"""
BGE-small-en-v1.5 semantic embeddings with run-scoped disk cache.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(
    texts: list[str],
    cache_path: Path | None = None,
    batch_size: int = 64,
) -> np.ndarray:
    """
    Embed a list of strings. Returns (N, 384) float32 array, L2-normalised.
    If cache_path exists, loads from disk. Otherwise computes and saves.
    """
    if cache_path and cache_path.exists():
        return np.load(str(cache_path)).astype(np.float32)

    model = _get_model()
    embeddings: np.ndarray = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
    ).astype(np.float32)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(cache_path), embeddings)

    return embeddings


def embed_reviews(
    reviews: list[dict],
    run_id: str = "dry-run",
    cache_dir: str = "data/output/.embed_cache",
) -> np.ndarray:
    """
    Embed the text_redacted field of each review.
    Cache is keyed by run_id so reruns are instant.
    """
    cache_path = Path(cache_dir) / f"{run_id}.npy"
    texts = [r.get("text_redacted", "") for r in reviews]
    return embed_texts(texts, cache_path=cache_path)
