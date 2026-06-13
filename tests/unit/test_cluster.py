"""Tests for pulse.analysis.cluster."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from pulse.analysis.cluster import cluster_reviews, classify_with_clustering


@pytest.fixture
def config():
    return SimpleNamespace(
        n_clusters=3,
        provider="groq",
        fallback_provider="gemini",
        model="llama-3.3-70b-versatile",
        fallback_model="gemini-2.5-flash-lite",
        temperature=0,
        max_retries=1,
        timeout_seconds=30,
    )


def _make_reviews(n: int) -> list[dict]:
    return [
        {
            "review_id": i,
            "text_redacted": f"Review number {i}",
            "rating": 3,
        }
        for i in range(n)
    ]


def _fake_embeddings(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    embs = rng.random((n, 32), dtype=np.float32)
    # L2-normalise to match real bge output
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return embs / norms


def test_cluster_reviews_adds_fields(config):
    n = 9
    reviews = _make_reviews(n)
    embs = _fake_embeddings(n)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        mock_llm.return_value = "App performance, bugs & reliability"
        result = cluster_reviews(reviews, embs, config, run_id="test")

    assert len(result) == n
    for r in result:
        assert "cluster_id" in r
        assert "cluster_theme" in r
        assert "cluster_confidence" in r
        assert 0 <= r["cluster_confidence"] <= 1
        assert r["cluster_id"] in range(config.n_clusters)


def test_cluster_reviews_theme_is_valid(config):
    from pulse.analysis.classify import THEME_LABELS
    n = 6
    reviews = _make_reviews(n)
    embs = _fake_embeddings(n)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        # Return a slightly fuzzy label — should still snap to canonical
        mock_llm.return_value = "Account Access Login"
        result = cluster_reviews(reviews, embs, config, run_id="test")

    for r in result:
        assert r["cluster_theme"] in THEME_LABELS


def test_cluster_reviews_k_capped_at_n(config):
    """If n < n_clusters, k should be capped at n."""
    reviews = _make_reviews(2)
    embs = _fake_embeddings(2)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        mock_llm.return_value = "Account access & login"
        result = cluster_reviews(reviews, embs, config, run_id="test")

    assert len(result) == 2
    # All cluster_ids must be in range(0, 2)
    assert all(r["cluster_id"] in (0, 1) for r in result)


def test_classify_with_clustering_output_schema(config):
    n = 9
    reviews = _make_reviews(n)
    embs = _fake_embeddings(n)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        mock_llm.return_value = "Trading, investing & crypto"
        result = classify_with_clustering(reviews, embs, config, run_id="test")

    assert len(result) == n
    for r in result:
        assert "theme" in r
        assert "confidence" in r
        assert r["theme"] == r["cluster_theme"]
        assert r["confidence"] == r["cluster_confidence"]


def test_cluster_reviews_llm_called_once_per_cluster(config):
    n = 9
    reviews = _make_reviews(n)
    embs = _fake_embeddings(n)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        mock_llm.return_value = "Account access & login"
        cluster_reviews(reviews, embs, config, run_id="test")

    # Should have been called exactly n_clusters times (one per cluster)
    assert mock_llm.call_count == config.n_clusters


def test_cluster_reviews_preserves_review_fields(config):
    reviews = [
        {"review_id": 10, "text_redacted": "can't login", "rating": 1, "platform": "App Store"},
    ]
    embs = _fake_embeddings(1)

    with patch("pulse.analysis.cluster.call_llm_text") as mock_llm:
        mock_llm.return_value = "Account access & login"
        result = cluster_reviews(reviews, embs, config, run_id="test")

    assert result[0]["review_id"] == 10
    assert result[0]["platform"] == "App Store"
    assert result[0]["rating"] == 1
