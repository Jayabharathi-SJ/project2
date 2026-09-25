"""
Virtual CFO API — Production Hardened Backend Application.

Phase 5 Hardened:
- Centralized production settings (backend.config)
- Structured & credential-redacting logging (backend.logging_config)
- Production-grade CORS policy (no wildcard credentials)
- Liveness (/health) and readiness (/health/ready) probes
- Magic byte validation for document uploads (%PDF-)
- Strict request validation and sanitized error responses
- Deterministic calculation protection
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.logging_config import logger
from database.checkpointer import check_postgres_connection
from models.asset import AssetAnalysisRequest
from rag.qdrant_store import check_qdrant_health
from services.asset_analysis_service import (
    analyze_asset_financial_options_async,
)
from services.llm_service import check_nvidia_health

# ---------------------------------------------------------------------------
# FastAPI Application Factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG or settings.APP_ENV != "production" else "/docs",
    redoc_url="/redoc" if settings.DEBUG or settings.APP_ENV != "production" else None,
)

# ---------------------------------------------------------------------------
# Production-Safe CORS Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

# ---------------------------------------------------------------------------
# Exception Handlers — Consistent, Sanitized Responses
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic request validation errors into a clean, predictable response.

    Pydantic v2 ``exc.errors()`` may contain non-JSON-serializable objects
    inside the ``ctx`` dict (e.g. ``Decimal``, ``ValueError``, custom types).
    We sanitize every error dict so that ``JSONResponse`` never encounters a
    ``TypeError`` at serialization time.
    """

    def _sanitize_ctx(ctx: dict) -> dict:
        """Recursively convert non-primitive context values to strings."""
        sanitized: dict = {}
        for key, value in ctx.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
                    for v in value
                ]
            else:
                sanitized[key] = str(value)
        return sanitized

    sanitized_details = []
    human_messages = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        human_messages.append(f"{field}: {err.get('msg', 'Invalid input')}")

        clean_err: dict = {
            "loc": err.get("loc", []),
            "msg": err.get("msg", "Invalid input"),
            "type": err.get("type", "value_error"),
        }
        if "ctx" in err and isinstance(err["ctx"], dict):
            clean_err["ctx"] = _sanitize_ctx(err["ctx"])
        sanitized_details.append(clean_err)

    logger.warning("Request validation failed on %s: %s", request.url.path, human_messages)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "error_type": "validation_error",
            "detail": sanitized_details,
            "messages": human_messages,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensure HTTP exceptions adhere to uniform error structure."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "detail": exc.detail,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Sanitize internal errors to prevent leaking stack traces or credentials."""
    correlation_id = f"err-{uuid.uuid4().hex[:8]}"
    logger.error(
        "Unhandled exception [%s] on %s: %s",
        correlation_id,
        request.url.path,
        str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "correlation_id": correlation_id,
            "detail": (
                "CFO analysis failed due to an internal processing error. "
                f"Please try again or contact support with reference: {correlation_id}"
            ),
        },
    )


# ---------------------------------------------------------------------------
# Static Frontend Mounting
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(_FRONTEND_DIR), html=True),
        name="dashboard",
    )


# ---------------------------------------------------------------------------
# Health & Diagnostic Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
async def root():
    """Service identity endpoint for routing and load balancer checks."""
    return {
        "message": "Virtual CFO API is running",
        "version": settings.APP_VERSION,
        "status": "success",
    }


@app.get("/health", tags=["meta"])
async def health():
    """
    Lightweight liveness probe.
    Returns 200 immediately if the HTTP worker is operational.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/health/ready", tags=["meta"])
async def readiness():
    """
    Readiness probe for container orchestration / cloud deployment.
    Evaluates backend dependencies (PostgreSQL, Qdrant, NVIDIA configuration)
    without running expensive queries.
    """
    db_ok, db_detail = check_postgres_connection(timeout_seconds=2)
    qdrant_ok, qdrant_detail = check_qdrant_health()
    nvidia_ok, nvidia_detail = check_nvidia_health()

    # The service can run in degraded mode with in-memory rules if external DBs delay
    overall_status = "ready" if (db_ok and qdrant_ok) else "degraded"

    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "dependencies": {
            "postgresql": {"ready": db_ok, "detail": db_detail},
            "qdrant": {"ready": qdrant_ok, "detail": qdrant_detail},
            "nvidia_llm": {"ready": nvidia_ok, "detail": nvidia_detail},
        },
    }


# ---------------------------------------------------------------------------
# RAG Diagnostics & Seeding Endpoints
# ---------------------------------------------------------------------------

@app.get("/rag/status", tags=["rag"])
async def rag_status():
    """Diagnostic endpoint reporting Qdrant legal collection status."""
    from rag.qdrant_store import COLLECTION_NAME, create_qdrant_client
    try:
        client = create_qdrant_client()
        try:
            exists = client.collection_exists(COLLECTION_NAME)
            count = 0
            if exists:
                info = client.get_collection(COLLECTION_NAME)
                count = getattr(info, "points_count", None) or 0
            return {
                "collection_name": COLLECTION_NAME,
                "exists": exists,
                "points_count": count,
                "status": "ready" if (exists and count > 0) else "empty",
            }
        finally:
            client.close()
    except Exception as exc:
        return {
            "collection_name": COLLECTION_NAME,
            "status": "unavailable",
            "error": str(exc),
        }


@app.post("/rag/seed", tags=["rag"])
async def rag_seed():
    """Seed Qdrant legal collection from official BNM 2026 legal guide."""
    from rag.qdrant_store import create_qdrant_client, ensure_legal_collection_populated
    try:
        client = create_qdrant_client()
        try:
            count = ensure_legal_collection_populated(client)
            return {
                "status": "success",
                "message": f"Successfully ensured {count} legal documents indexed in Qdrant.",
                "points_count": count,
            }
        finally:
            client.close()
    except Exception as exc:
        logger.error("Manual RAG seeding failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed Qdrant collection: {str(exc)}",
        ) from exc


# ---------------------------------------------------------------------------
# Core Analysis Endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", tags=["analysis"])
async def analyze_asset(
    request: AssetAnalysisRequest,
):
    """
    Run a full multi-agent financial analysis on a proposed asset acquisition.

    Returns deterministic financial calculations, BNM 2026 legal validation,
    and an AI-generated CFO executive summary.
    """
    try:
        logger.info(
            "Executing CFO analysis for asset: %s (Price: RM %s)",
            request.asset_name,
            request.asset_price,
        )

        result = await analyze_asset_financial_options_async(
            asset_name=request.asset_name,
            asset_price=request.asset_price,
            down_payment=request.down_payment,
            hp_period_months=request.hp_period_months,
            hp_interest_rate=request.hp_interest_rate,
            hp_rate_type=request.hp_rate_type,
            cash_discount=request.cash_discount,
            lease_period_months=request.lease_period_months,
            lease_monthly_payment=request.lease_monthly_payment,
        )

        return {
            "status": "success",
            "message": "Asset analysis completed successfully.",
            "analysis": result,
            "thread_id": result.get("thread_id"),
        }

    except ValueError as exc:
        logger.warning("Input validation rejection: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.error("CFO analysis execution failed: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CFO analysis failed. Please check your inputs and try again.",
        ) from exc


# ---------------------------------------------------------------------------
# Multimodal Document Processing Endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze-document", tags=["multimodal"])
async def analyze_document(
    file: UploadFile = File(...),
):
    """
    Upload a PDF financial quotation (HP letter, invoice, etc.) and extract
    asset/financing parameters for pre-filling the analysis form.

    Security validations:
    - Enforces MIME type check
    - Enforces file size cap (default 10 MB)
    - Verifies %PDF- magic bytes header to block spoofed/malicious binaries
    - Sanitizes filename to protect against path traversal
    """
    # 1. Content-Type Header Check
    if file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: {file.content_type!r}. "
                "Only PDF documents are accepted."
            ),
        )

    # 2. File Size & Content Ingestion
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(pdf_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        file_mb = len(pdf_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File is too large ({file_mb:.1f} MB). "
                f"Maximum allowed size is {max_mb:.0f} MB."
            ),
        )

    # 3. Magic Byte Verification (prevent disguised malicious files)
    if not pdf_bytes.startswith(settings.PDF_MAGIC_BYTES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Invalid PDF file signature. The file contents do not match "
                "a standard PDF specification."
            ),
        )

    # 4. Safe Filename Extraction
    safe_filename = Path(file.filename or "upload.pdf").name

    # 5. Multimodal Parser Availability Check
    try:
        from services.multimodal_parser import parse_financial_document_pdf
    except ImportError as err:
        logger.error("pypdf is not available for document parsing: %s", err)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Multimodal parser is not available. Install pypdf: pip install pypdf",
        ) from err

    # 6. Parse and Validate
    try:
        extraction = parse_financial_document_pdf(
            pdf_bytes=pdf_bytes,
        )
    except Exception as exc:
        logger.error("Failed parsing PDF '%s': %s", safe_filename, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Document parsing failed. The PDF may be encrypted, "
                "corrupted, or contains unreadable streams."
            ),
        ) from exc

    return {
        "status": "success",
        "document_name": safe_filename,
        "extraction": extraction,
        "user_action_required": (
            "Review and confirm the extracted values before running analysis. "
            "Do not rely on OCR output without verification."
        ),
    }