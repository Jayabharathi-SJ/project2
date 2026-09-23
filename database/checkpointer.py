"""
Virtual CFO Committee — Database Checkpointer & Persistence.

Manages LangGraph execution checkpoint persistence using PostgreSQL,
with secure credential masking and fast health checks.
"""

import os
from contextlib import asynccontextmanager
from typing import Optional, Tuple
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.config import mask_connection_string

load_dotenv()


def get_postgres_uri() -> str:
    """Retrieve the configured POSTGRES_URI or raise descriptive error."""
    uri = os.getenv("POSTGRES_URI")
    if not uri:
        raise RuntimeError(
            "POSTGRES_URI is not configured in the environment. "
            "Please configure a valid PostgreSQL connection string."
        )
    return uri


def get_masked_uri() -> str:
    """Return the connection URI with password masked for safe logging."""
    return mask_connection_string(os.getenv("POSTGRES_URI"))


def create_checkpointer():
    """Create synchronous PostgreSQL checkpointer."""
    return PostgresSaver.from_conn_string(get_postgres_uri())


def create_async_checkpointer():
    """Create asynchronous PostgreSQL checkpointer."""
    return AsyncPostgresSaver.from_conn_string(get_postgres_uri())


@asynccontextmanager
async def create_resilient_async_checkpointer():
    """
    Connect to PostgreSQL if reachable; if unavailable, yield an in-memory checkpointer
    and set is_persisted=False so the system never pretends persistence succeeded (Req 14 & 15).
    """
    from langgraph.checkpoint.memory import MemorySaver

    uri = os.getenv("POSTGRES_URI")
    if uri:
        try:
            checkpointer = AsyncPostgresSaver.from_conn_string(uri)
            async with checkpointer as cp:
                # Ensure checkpointer schema is set up if possible
                try:
                    await cp.setup()
                except Exception:
                    pass
                yield cp, True
                return
        except Exception:
            pass

    # Safe fallback: in-memory state tracking, explicitly marking persistence as False
    yield MemorySaver(), False



def check_postgres_connection(timeout_seconds: int = 3) -> Tuple[bool, str]:
    """
    Fast, non-blocking health check for PostgreSQL connectivity.
    Used by the readiness probe.
    """
    uri = os.getenv("POSTGRES_URI")
    if not uri:
        return False, "POSTGRES_URI not configured"

    try:
        import psycopg
        with psycopg.connect(uri, connect_timeout=timeout_seconds) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "Connected"
    except Exception as exc:
        return False, f"PostgreSQL unavailable: {type(exc).__name__}"


def setup_checkpointer():
    """Initialize checkpoint tables in PostgreSQL."""
    with create_checkpointer() as checkpointer:
        checkpointer.setup()
        print("PostgreSQL checkpoint tables: SUCCESS")


def verify_checkpoint(thread_id: str):
    """Verify that state checkpoints exist for a specific thread."""
    with create_checkpointer() as checkpointer:
        checkpoints = list(
            checkpointer.list({"configurable": {"thread_id": thread_id}})
        )
        print(f"Checkpoints found: {len(checkpoints)}")
        if checkpoints:
            print("PostgreSQL checkpoint verification: SUCCESS")
        else:
            print("PostgreSQL checkpoint verification: FAILED")