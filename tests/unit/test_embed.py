"""Tests for pulse.analysis.embed."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from pulse.analysis.embed import embed_texts, embed_reviews


@pytest.fixture
def mock_model():
    """Patch SentenceTransformer so no network/GPU required in unit tests."""
    import pulse.analysis.embed as embed_module
    fake = MagicMock()
    fake.encode.side_effect = lambda texts, **_: np.random.rand(len(texts), 384).astype(np.float32)
    with patch.object(embed_module, "_model", fake):
        yield fake


def test_embed_texts_returns_correct_shape(mock_model, tmp_path):
    texts = ["Review about login", "App crashes a lot", "Great transfers"]
    result = embed_texts(texts)
    assert result.shape == (3, 384)
    assert result.dtype == np.float32


def test_embed_texts_uses_cache(mock_model, tmp_path):
    texts = ["one", "two"]
    cache = tmp_path / "cache.npy"

    # First call — should compute and save
    r1 = embed_texts(texts, cache_path=cache)
    assert cache.exists()
    assert mock_model.encode.call_count == 1

    # Second call — should load from disk, not re-encode
    r2 = embed_texts(texts, cache_path=cache)
    assert mock_model.encode.call_count == 1  # still 1
    np.testing.assert_array_equal(r1, r2)


def test_embed_reviews_uses_text_redacted(mock_model, tmp_path):
    reviews = [
        {"text_redacted": "Can't log in"},
        {"text_redacted": "Transfer stuck"},
        {"text_redacted": ""},
    ]
    import pulse.analysis.embed as em
    with patch.object(em, "embed_texts", wraps=em.embed_texts) as mock_et:
        embed_reviews(reviews, run_id="test-run", cache_dir=str(tmp_path))
    # embed_texts should have been called with exactly the text_redacted values
    called_texts = mock_et.call_args[0][0]
    assert called_texts == ["Can't log in", "Transfer stuck", ""]


def test_embed_texts_cache_miss_then_hit_roundtrip(tmp_path):
    """Cache must persist and reload identical float32 data."""
    import pulse.analysis.embed as em

    fake_model = MagicMock()
    fake_embs = np.random.rand(2, 384).astype(np.float32)
    fake_model.encode.return_value = fake_embs

    with patch.object(em, "_model", fake_model):
        cache = tmp_path / "sub" / "embeddings.npy"
        r1 = em.embed_texts(["a", "b"], cache_path=cache)
        r2 = em.embed_texts(["a", "b"], cache_path=cache)

    np.testing.assert_array_almost_equal(r1, r2)
    assert fake_model.encode.call_count == 1
