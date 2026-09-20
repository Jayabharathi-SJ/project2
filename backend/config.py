"""
Virtual CFO Committee — Centralized Production Configuration.

Centralizes environment configuration, database connection parameters,
vector store parameters, LLM endpoints, security policies, and CORS.
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from dotenv import load_dotenv

# Load .env file from project root if present
_ROOT_DIR = Path(__file__).parent.parent
load_dotenv(_ROOT_DIR / ".env")


def mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask sensitive string leaving only the prefix visible."""
    if not value:
        return "<not-configured>"
    if len(value) <= visible_chars:
        return "****"
    return f"{value[:visible_chars]}...****"


def mask_connection_string(uri: Optional[str]) -> str:
    """Mask password inside connection URI (e.g. postgresql://user:pwd@host:port/db)."""
    if not uri:
        return "<not-configured>"
    return re.sub(r":([^:@]+)@", r":****@", uri)


class Settings:
    """Production application settings with environment overrides."""

    APP_NAME: str = "Virtual CFO API"
    APP_DESCRIPTION: str = (
        "Multimodal Autonomous Financial Research Agent — "
        "Malaysian Hire-Purchase 2026 Legal & Financial Engine"
    )
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "production").lower()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # --- CORS Configuration ---
    # Parse comma-separated origins, strip whitespace, remove empty entries
    _RAW_CORS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost,http://localhost:3000,http://localhost:5500,"
        "http://localhost:8000,http://127.0.0.1,http://127.0.0.1:3000,"
        "http://127.0.0.1:5500,http://127.0.0.1:8000",
    )

    @property
    def CORS_ORIGINS(self) -> List[str]:
        origins = [orig.strip() for orig in self._RAW_CORS.split(",") if orig.strip()]
        return origins or ["http://localhost:8000"]

    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        # Starlette prohibits allow_credentials=True when wildcard '*' is in origins
        if "*" in self.CORS_ORIGINS:
            return False
        return True

    # --- PostgreSQL Checkpointer ---
    POSTGRES_URI: str = os.getenv("POSTGRES_URI", "")

    @property
    def POSTGRES_URI_MASKED(self) -> str:
        return mask_connection_string(self.POSTGRES_URI)

    # --- NVIDIA AI Foundation ---
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_MODEL: str = os.getenv(
        "NVIDIA_MODEL",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    )
    NVIDIA_BASE_URL: str = os.getenv(
        "NVIDIA_BASE_URL",
        "https://integrate.api.nvidia.com/v1",
    )
    NVIDIA_TIMEOUT: float = float(os.getenv("NVIDIA_TIMEOUT", "15.0"))

    @property
    def NVIDIA_API_KEY_MASKED(self) -> str:
        return mask_secret(self.NVIDIA_API_KEY, visible_chars=6)

    # --- Qdrant Vector Store ---
    QDRANT_PATH: Optional[str] = os.getenv("QDRANT_PATH", "./qdrant_data")
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", None)
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    QDRANT_COLLECTION_NAME: str = os.getenv(
        "QDRANT_COLLECTION_NAME",
        "legal_documents",
    )

    # --- File Upload Security ---
    MAX_UPLOAD_SIZE_BYTES: int = int(
        os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024))
    )  # Default 10 MB
    ALLOWED_UPLOAD_TYPES: Set[str] = {"application/pdf"}

    # Magic byte header signature for PDF files
    PDF_MAGIC_BYTES: bytes = b"%PDF-"


settings = Settings()
