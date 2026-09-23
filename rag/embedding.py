import os
import re
import math
import hashlib
from typing import List, Optional


MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
_model: Optional[object] = None
_model_failed: bool = False


def is_memory_constrained() -> bool:
    """Check if process is running under constrained memory (e.g. Render 512MB free tier)."""
    if os.getenv("FORCE_LOCAL_EMBEDDINGS", "0") == "1":
        return False
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path, "r") as f:
                val = f.read().strip()
                if val and val != "max":
                    limit_bytes = int(val)
                    if limit_bytes <= 629145600:  # 600 MiB
                        return True
        except Exception:
            pass
    return False


def _deterministic_fallback_embedding(text: str, dim: int = EMBEDDING_DIMENSION) -> List[float]:
    """
    Deterministic, pure-Python 384-dimensional text embedding.
    Extracts words and character 3-grams, hashes them into `dim` buckets,
    and returns an L2-normalized vector. Produces high cosine similarity
    for overlapping legal/financial concepts without requiring C-extension libraries.
    """
    vec = [0.0] * dim
    clean_text = text.lower()
    words = re.findall(r"\b\w+\b", clean_text)

    # 1. Word unigram hashing
    for word in words:
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
        vec[idx] += sign * 1.5

    # 2. Character 3-gram hashing for subword robustness
    for i in range(len(clean_text) - 2):
        trigram = clean_text[i : i + 3]
        h = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
        vec[idx] += sign * 0.5

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        return [v / norm for v in vec]
    return vec


def get_embedding_model():
    """Lazily load and return the SentenceTransformer model with constrained CPU threads."""
    global _model, _model_failed
    if _model_failed:
        return None
    if _model is None:
        if is_memory_constrained():
            _model_failed = True
            return None
        try:
            import torch
            torch.set_num_threads(1)
            from sentence_transformers import SentenceTransformer

            try:
                # Prioritize local cache to avoid online hub latency/timeouts
                _model = SentenceTransformer(MODEL_NAME, local_files_only=True)
            except Exception:
                _model = SentenceTransformer(MODEL_NAME)
        except Exception:
            _model_failed = True
            return None
    return _model


def generate_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    model = get_embedding_model()
    if model is not None:
        try:
            embedding = model.encode(
                text,
                normalize_embeddings=True,
            )
            return embedding.tolist()
        except Exception:
            pass

    return _deterministic_fallback_embedding(text)


def get_embedding_dimension() -> int:
    return EMBEDDING_DIMENSION

