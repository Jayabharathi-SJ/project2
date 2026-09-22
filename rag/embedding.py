from typing import List, Optional
import os


MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
_model: Optional[object] = None


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


def get_embedding_model():
    """Lazily load and return the SentenceTransformer model with constrained CPU threads."""
    global _model
    if _model is None:
        if is_memory_constrained():
            raise RuntimeError(
                "Local SentenceTransformer embedding model is disabled because container "
                "memory is constrained (<= 600MB, Render 512MB limit). "
                "Use in-memory statutory rules fallback or provision a service with >= 1GB RAM."
            )
        import torch
        torch.set_num_threads(1)
        from sentence_transformers import SentenceTransformer

        try:
            # Prioritize local cache to avoid online hub latency/timeouts
            _model = SentenceTransformer(MODEL_NAME, local_files_only=True)
        except Exception:
            _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    model = get_embedding_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


def get_embedding_dimension() -> int:
    return EMBEDDING_DIMENSION
