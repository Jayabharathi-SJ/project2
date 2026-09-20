"""
Tests for Phase 5 — Production Backend Hardening.

Covers:
- Centralized configuration and secret masking
- Log credential redaction (passwords, API keys, Bearer tokens)
- Liveness (/health) and readiness (/health/ready) probes
- Document upload security (%PDF- magic byte verification, size limits, empty files)
- Exception handler sanitization and error format consistency
- Health checks for database, vector store, and LLM services
- .gitignore protection against secret exposure
"""

import io
import logging
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.config import mask_connection_string, mask_secret, settings
from backend.logging_config import SensitiveDataFilter
from backend.main import app
from database.checkpointer import check_postgres_connection
from rag.qdrant_store import check_qdrant_health
from services.llm_service import check_nvidia_health

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Configuration & Secret Masking Tests
# ---------------------------------------------------------------------------

class TestConfigurationAndSecrets:
    """Verify that credentials are never exposed in plaintext."""

    def test_mask_secret(self):
        secret = "nvapi-hgKFv0xY4eQf8xj7K2BfZhrc"
        masked = mask_secret(secret, visible_chars=5)
        assert "nvapi" in masked
        assert "****" in masked
        assert "hgKFv0xY4eQf8xj7K2BfZhrc" not in masked

    def test_mask_secret_empty(self):
        assert mask_secret(None) == "<not-configured>"
        assert mask_secret("") == "<not-configured>"

    def test_mask_connection_string(self):
        uri = "postgresql://postgres:mySuperSecret123@localhost:5432/virtual_cfo"
        masked = mask_connection_string(uri)
        assert "mySuperSecret123" not in masked
        assert "postgresql://postgres:****@localhost:5432/virtual_cfo" == masked

    def test_mask_connection_string_empty(self):
        assert mask_connection_string(None) == "<not-configured>"

    def test_cors_credentials_safety_with_wildcard(self):
        with patch.object(settings, "_RAW_CORS", "*"):
            assert settings.CORS_ORIGINS == ["*"]
            assert settings.CORS_ALLOW_CREDENTIALS is False

    def test_cors_credentials_allowed_with_explicit_origins(self):
        with patch.object(settings, "_RAW_CORS", "http://localhost:3000,http://127.0.0.1:8000"):
            assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:8000"]
            assert settings.CORS_ALLOW_CREDENTIALS is True


# ---------------------------------------------------------------------------
# 2. Logging Redaction Tests
# ---------------------------------------------------------------------------

class TestLoggingRedaction:
    """Verify that sensitive data filters scrub credentials before output."""

    def test_sensitive_data_filter_redacts_db_password(self):
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Connecting to postgresql://postgres:superSecretPass@localhost:5432/virtual_cfo",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert "superSecretPass" not in record.msg
        assert "postgresql://postgres:****@localhost:5432/virtual_cfo" in record.msg

    def test_sensitive_data_filter_redacts_nvidia_api_key(self):
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Sending request with API key nvapi-abcdef1234567890xyz",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert "abcdef1234567890xyz" not in record.msg
        assert "nvapi-****" in record.msg

    def test_sensitive_data_filter_redacts_bearer_token(self):
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Authorization header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in record.msg
        assert "Bearer ****" in record.msg


# ---------------------------------------------------------------------------
# 3. Health & Readiness Probe Tests
# ---------------------------------------------------------------------------

class TestHealthAndReadiness:
    """Verify liveness and readiness probe endpoints."""

    def test_liveness_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_readiness_endpoint(self):
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ready", "degraded")
        assert "dependencies" in data
        assert "postgresql" in data["dependencies"]
        assert "qdrant" in data["dependencies"]
        assert "nvidia_llm" in data["dependencies"]

    def test_check_postgres_connection_resilience(self):
        # Should return boolean tuple without raising unhandled exception
        is_ok, detail = check_postgres_connection(timeout_seconds=1)
        assert isinstance(is_ok, bool)
        assert isinstance(detail, str)

    def test_check_qdrant_health_resilience(self):
        is_ok, detail = check_qdrant_health()
        assert isinstance(is_ok, bool)
        assert isinstance(detail, str)

    def test_check_nvidia_health_resilience(self):
        is_ok, detail = check_nvidia_health()
        assert isinstance(is_ok, bool)
        assert isinstance(detail, str)


# ---------------------------------------------------------------------------
# 4. Document Security & Magic Byte Verification Tests
# ---------------------------------------------------------------------------

class TestDocumentSecurity:
    """Verify file upload validations, magic byte guards, and size limits."""

    def test_rejects_non_pdf_mime_type(self):
        files = {"file": ("malicious.exe", b"%PDF-dummy", "application/x-dosexec")}
        response = client.post("/analyze-document", files=files)
        assert response.status_code == 415

    def test_rejects_spoofed_pdf_magic_bytes(self):
        # File has application/pdf MIME type but malicious binary/script content (no %PDF- header)
        spoofed_content = b"echo 'malicious script'; exit 0;"
        files = {"file": ("fake.pdf", spoofed_content, "application/pdf")}
        response = client.post("/analyze-document", files=files)
        assert response.status_code == 415
        assert "Invalid PDF file signature" in response.json()["detail"]

    def test_rejects_empty_file(self):
        files = {"file": ("empty.pdf", b"", "application/pdf")}
        response = client.post("/analyze-document", files=files)
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_rejects_file_exceeding_size_limit(self):
        # Create bytes larger than configured limit
        large_bytes = b"%PDF-" + b"0" * 1000
        with patch.object(settings, "MAX_UPLOAD_SIZE_BYTES", 500):
            files = {"file": ("large.pdf", large_bytes, "application/pdf")}
            response = client.post("/analyze-document", files=files)
            assert response.status_code == 413
            assert "too large" in response.json()["detail"].lower()

    def test_accepts_valid_pdf_magic_bytes(self):
        valid_minimal_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
        )
        files = {"file": ("valid.pdf", valid_minimal_pdf, "application/pdf")}
        response = client.post("/analyze-document", files=files)
        assert response.status_code == 200
        assert response.json()["status"] == "success"


# ---------------------------------------------------------------------------
# 5. Security & Repository Hygiene Tests
# ---------------------------------------------------------------------------

class TestRepositorySecurity:
    """Verify repository configuration and absence of tracked secrets."""

    def test_gitignore_ignores_env_file(self):
        root = Path(__file__).parent.parent
        gitignore_path = root / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text(encoding="utf-8")
        assert ".env" in content
        assert ".venv" in content

    def test_env_example_contains_no_real_secrets(self):
        root = Path(__file__).parent.parent
        env_example = root / ".env.example"
        assert env_example.exists()
        content = env_example.read_text(encoding="utf-8")
        assert "abhi24" not in content  # Real password purged
        assert "your-key-here" in content or "your-secure-password" in content
