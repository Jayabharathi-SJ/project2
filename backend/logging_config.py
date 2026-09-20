"""
Virtual CFO Committee — Structured & Redacting Logging Configuration.

Ensures application logs provide actionable operational observability
without ever leaking passwords, connection credentials, or API keys.
"""

import logging
import re
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that scrubs credentials, connection passwords,
    and API bearer tokens from all log messages.
    """

    # Patterns to redact
    _PATTERNS = [
        # Database passwords in URIs: postgresql://user:pwd@host
        (re.compile(r"://([^:@\s]+):([^@\s]+)@"), r"://\1:****@"),
        # NVIDIA API Keys: nvapi-...
        (re.compile(r"nvapi-[A-Za-z0-9_\-]{10,}"), r"nvapi-****"),
        # Bearer tokens in headers: Bearer ...
        (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), r"Bearer ****"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self._PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        if record.args:
            cleaned_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self._PATTERNS:
                        arg = pattern.sub(replacement, arg)
                cleaned_args.append(arg)
            record.args = tuple(cleaned_args)

        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the root application logger."""
    logger = logging.getLogger("virtual_cfo")
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
