from typing import List, Optional
import os


MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
_model: Optional[object] = None


def get_embedding_model():
    """Lazily load and return the SentenceTransformer model with constrained CPU threads."""
    global _model
    if _model is None:
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
