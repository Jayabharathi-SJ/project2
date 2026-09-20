from typing import List, Optional
import os

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Lazily load and return the SentenceTransformer model."""
    global _model
    if _model is None:
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
    return get_embedding_model().get_sentence_embedding_dimension()