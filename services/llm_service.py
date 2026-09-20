"""
Virtual CFO Committee — NVIDIA NIM LLM Integration Service.

Provides executive explanation synthesis with strict secret protection,
timeout handling, response validation, and independent deterministic isolation.
"""

import os
from typing import Tuple
import httpx
from dotenv import load_dotenv

from backend.config import mask_secret

load_dotenv()

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def get_nvidia_api_key() -> str:
    return os.getenv("NVIDIA_API_KEY", "")


def get_nvidia_model() -> str:
    return os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")


def get_nvidia_api_url() -> str:
    """Retrieve full chat completions endpoint, honoring NVIDIA_BASE_URL override."""
    base = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def check_nvidia_health() -> Tuple[bool, str]:
    """
    Lightweight readiness check for the NVIDIA LLM service.
    Verifies that the API key and model identifier are configured.
    """
    key = get_nvidia_api_key()
    if not key:
        return False, "NVIDIA_API_KEY not configured (fallback mode active)"
    if not get_nvidia_model():
        return False, "NVIDIA_MODEL not configured"
    return True, f"Configured ({get_nvidia_model()})"


async def ask_nvidia(prompt: str) -> str:
    """
    Send a prompt to the NVIDIA NIM chat completion API.

    Returns:
        str: Model response text.

    Raises:
        RuntimeError: If configuration or API request fails.
        ValueError: If prompt is empty.
    """
    api_key = get_nvidia_api_key()
    model = get_nvidia_model()

    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not configured.")

    if not model:
        raise RuntimeError("NVIDIA_MODEL is not configured.")

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }

    try:
        timeout_seconds = float(os.getenv("NVIDIA_TIMEOUT", "15.0"))
    except ValueError:
        timeout_seconds = 15.0

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                get_nvidia_api_url(),
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"NVIDIA API request timed out after {timeout_seconds} seconds."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"NVIDIA API connection error: {type(exc).__name__}"
        ) from exc

    if response.status_code != 200:
        # Sanitize error: never leak response.text if it might echo headers/secrets
        raise RuntimeError(
            f"NVIDIA API request failed with status code {response.status_code}."
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "Invalid response structure received from NVIDIA API."
        ) from exc

    if not content or not content.strip():
        raise RuntimeError(
            "NVIDIA API returned an empty response."
        )

    return content.strip()