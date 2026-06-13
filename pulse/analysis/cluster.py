"""
K-means clustering of review embeddings with per-cluster LLM theme labeling.
One LLM text call per cluster (k calls total) instead of batched per-review calls.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans  # type: ignore

from pulse.analysis.classify import THEME_LABELS, _closest_theme
from pulse.utils.llm import call_llm_text
from pulse.utils.logging import log

_THEME_LIST_STR = "\n".join(f"- {t}" for t in THEME_LABELS)


def _label_cluster(rep_texts: list[str], config: Any) -> str:
    """
    Call the LLM once with up to 5 representative review snippets.
    Returns the closest matching THEME_LABEL.
    """
    snippets = "\n".join(f"- {t[:200]}" for t in rep_texts[:5])
    prompt = (
        "These app-store reviews share a common topic:\n\n"
        f"{snippets}\n\n"
        "Pick the single best-matching theme from this exact list "
        "(reply with the theme name only — no explanation):\n\n"
        f"{_THEME_LIST_STR}"
    )
    raw = call_llm_text(prompt, "", config).strip().strip('"').strip("'")
    return _closest_theme(raw)


def cluster_reviews(
    reviews: list[dict],
    embeddings: np.ndarray,
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    1. Run K-means (k = config.n_clusters, default 8).
    2. Label each cluster with one LLM text call.
    3. Assign cluster_theme + cluster_confidence to every review.

    Returns reviews annotated with:
      cluster_id         : int
      cluster_theme      : str  (one of THEME_LABELS)
      cluster_confidence : float  (cosine sim to centroid, [0, 1])
    """
    n = len(reviews)
    k = min(getattr(config, "n_clusters", 8), n)

    km = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels: np.ndarray = km.fit_predict(embeddings)     # (N,) int
    centroids: np.ndarray = km.cluster_centers_         # (k, dim)

    # Normalise centroids for cosine similarity (embeddings are already L2-normed)
    centroid_norms = np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-9
    centroids_normed = centroids / centroid_norms       # (k, dim)

    cluster_themes: dict[int, str] = {}

    for cid in range(k):
        mask = labels == cid
        cluster_idx = np.where(mask)[0]
        cluster_embs = embeddings[cluster_idx]          # (m, dim)

        # Cosine sims to centroid; pick top-5 most representative
        sims = cluster_embs @ centroids_normed[cid]
        top_local = np.argsort(sims)[::-1][:5]
        top_global = cluster_idx[top_local]
        rep_texts = [reviews[i].get("text_redacted", "") for i in top_global]

        theme = _label_cluster(rep_texts, config)
        cluster_themes[cid] = theme

        log(
            run_id, "cluster", "cluster_labeled",
            cluster_id=cid,
            theme=theme,
            size=int(mask.sum()),
            avg_cosine_sim=round(float(sims.mean()), 3),
        )

    # Compute per-review cosine similarity to its cluster centroid
    all_sims = (embeddings * centroids_normed[labels]).sum(axis=1)  # (N,)

    annotated: list[dict] = []
    for i, review in enumerate(reviews):
        cid = int(labels[i])
        confidence = float(np.clip(all_sims[i], 0.0, 1.0))
        annotated.append({
            **review,
            "cluster_id": cid,
            "cluster_theme": cluster_themes[cid],
            "cluster_confidence": round(confidence, 3),
        })

    log(
        run_id, "cluster", "cluster_complete",
        n_clusters=k,
        themes_assigned=sorted(set(cluster_themes.values())),
    )

    return annotated


def classify_with_clustering(
    redacted_reviews: list[dict],
    embeddings: np.ndarray,
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    Full clustering-based classification.
    Returns the same schema as classify_reviews(): adds 'theme' and 'confidence'.
    """
    from pulse.utils.llm import check_api_key
    check_api_key(config)

    clustered = cluster_reviews(redacted_reviews, embeddings, config, run_id=run_id)

    themed: list[dict] = []
    for review in clustered:
        themed.append({
            **review,
            "theme":      review["cluster_theme"],
            "confidence": review["cluster_confidence"],
        })

    log(
        run_id, "classify", "classify_complete",
        method="clustering",
        total_submitted=len(redacted_reviews),
        classified=len(themed),
        unclassified=0,
    )

    return themed
