from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from pulse.utils.llm import (
    call_llm,
    check_api_key,
    ContextOverflowError,
    JSONParseError,
    SafetyRefusalError,
)
from pulse.utils.logging import log

THEME_LABELS = [
    "Account access & login",
    "Onboarding & verification",
    "Transfers, deposits & withdrawals",
    "Trading, investing & crypto",
    "App performance, bugs & reliability",
    "Customer support & issue resolution",
    "Fees, pricing & product communication",
    "Tax, statements & documents",
]

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _closest_theme(label: str) -> str:
    matches = difflib.get_close_matches(label, THEME_LABELS, n=1, cutoff=0.3)
    return matches[0] if matches else THEME_LABELS[0]


def _build_batch_prompt(reviews: list[dict], config) -> str:
    max_chars = getattr(config, "max_review_chars", 2000)
    lines = []
    for i, r in enumerate(reviews):
        text = r.get("text_redacted", "")[:max_chars]
        lines.append(f"Review {i}: <review_text>{text}</review_text>")
    return "\n".join(lines)


def _call_classify_batch(
    batch: list[dict],
    config,
    run_id: str,
    strict: bool = False,
) -> list[dict]:
    """Call LLM for one batch; return list of raw classification dicts."""
    system_prompt = _load_prompt(
        "classify_themes_strict.txt" if strict else "classify_themes.txt"
    )
    prompt = _build_batch_prompt(batch, config)
    result = call_llm(prompt, system_prompt, config)
    if not isinstance(result, list):
        if isinstance(result, dict):
            # LLM may wrap the array: {"reviews": [...]} or {"classifications": [...]}
            for v in result.values():
                if isinstance(v, list):
                    result = v
                    break
            else:
                result = [result]  # genuine single-review dict
        else:
            result = [result]
    return result


def _validate_and_fix(
    raw: list[dict],
    batch: list[dict],
    config,
    run_id: str,
) -> tuple[list[dict], list[dict]]:
    """
    Validate classification results. Returns (valid_results, reviews_to_retry).
    Indices in valid_results are batch-relative (0 to len(batch)-1).
    Handles EC-19 (invalid theme) and EC-20 (missing indices).
    """
    valid: list[dict] = []
    responded_indices: set[int] = set()

    for entry in raw:
        idx = entry.get("review_index")
        theme = entry.get("theme", "")
        confidence = entry.get("confidence", 0.0)

        if idx is None or not isinstance(idx, int):
            continue
        # Only accept batch-relative indices (0 to len(batch)-1)
        if not (0 <= idx < len(batch)):
            continue

        responded_indices.add(idx)

        # Validate theme (EC-19)
        if theme not in THEME_LABELS:
            closest = _closest_theme(theme)
            log(run_id, "classify", "invalid_theme_fallback",
                original=theme, fallback=closest, review_index=idx)
            theme = closest

        # Coerce confidence
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        valid.append({
            "review_index": idx,  # batch-relative; caller remaps to global
            "theme": theme,
            "confidence": confidence,
        })

    # EC-20: detect missing batch-relative indices → collect for re-queue
    submitted_indices = set(range(len(batch)))
    missing_indices = submitted_indices - responded_indices
    if missing_indices:
        log(run_id, "classify", "missing_indices_detected",
            missing=sorted(missing_indices), will_retry=True)
        to_retry = [batch[i] for i in sorted(missing_indices)]
    else:
        to_retry = []

    return valid, to_retry


def classify_reviews(
    redacted_reviews: list[dict],
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    Classify each redacted review into one of 8 themes.
    Returns list of ThemedReview dicts (extends RedactedReview with theme + confidence).
    """
    check_api_key(config)

    batch_size = getattr(config, "batch_size", 50)
    all_results: dict[int, dict] = {}  # review_id → classification result

    # Tag each review with its batch index for missing-index tracking
    tagged = []
    for i, r in enumerate(redacted_reviews):
        tagged.append({**r, "_batch_index": i})

    def process_batch(batch: list[dict], strict: bool = False, _retry_depth: int = 0) -> list[dict]:
        """
        Process one batch; handle context overflow splitting (EC-39).
        Returns results with review_index remapped to global _batch_index.
        """
        try:
            raw = _call_classify_batch(batch, config, run_id, strict=strict)
        except ContextOverflowError:
            if len(batch) <= 1:
                log(run_id, "classify", "batch_too_small_to_split",
                    review_id=batch[0].get("review_id"))
                return []
            mid = len(batch) // 2
            log(run_id, "classify", "context_overflow_splitting", batch_size=len(batch))
            return process_batch(batch[:mid]) + process_batch(batch[mid:])
        except SafetyRefusalError:
            log(run_id, "classify", "safety_refusal_skipping_batch")
            return []
        except (JSONParseError, Exception) as exc:
            log(run_id, "classify", "batch_error", error=str(exc))
            return []

        valid, to_retry = _validate_and_fix(raw, batch, config, run_id)

        # Remap batch-relative review_index → global _batch_index (EC-20 fix for multi-batch)
        for res in valid:
            res["review_index"] = batch[res["review_index"]]["_batch_index"]

        # EC-20: re-queue missing reviews (one retry only to avoid infinite loops)
        if to_retry and _retry_depth == 0:
            requeued = process_batch(to_retry, strict=True, _retry_depth=1)
            valid.extend(requeued)
        elif to_retry:
            log(run_id, "classify", "missing_indices_dropped",
                count=len(to_retry), reason="retry limit reached")

        return valid

    for batch_start in range(0, len(tagged), batch_size):
        batch = tagged[batch_start: batch_start + batch_size]
        batch_results = process_batch(batch)
        for res in batch_results:
            all_results[res["review_index"]] = res

    # Merge classification back into review records
    themed: list[dict] = []
    for i, review in enumerate(redacted_reviews):
        result = all_results.get(i)
        if result is None:
            log(run_id, "classify", "review_unclassified", review_id=review.get("review_id"))
            continue
        themed.append({
            **review,
            "theme": result["theme"],
            "confidence": result["confidence"],
        })

    log(run_id, "classify", "classify_complete",
        total_submitted=len(redacted_reviews),
        classified=len(themed),
        unclassified=len(redacted_reviews) - len(themed))

    return themed


def rank_themes(
    themed_reviews: list[dict],
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    Aggregate by theme; sort by volume DESC → avg_rating ASC → alphabetical.
    Returns list of ThemeSummary dicts.
    """
    max_themes = getattr(config, "max_themes", 5)
    counts: dict[str, int] = {}
    rating_sums: dict[str, float] = {}

    for r in themed_reviews:
        theme = r["theme"]
        rating = float(r.get("rating", 3))
        counts[theme] = counts.get(theme, 0) + 1
        rating_sums[theme] = rating_sums.get(theme, 0.0) + rating

    summaries = []
    for theme, count in counts.items():
        avg_rating = rating_sums[theme] / count
        summaries.append({
            "theme": theme,
            "review_count": count,
            "avg_rating": round(avg_rating, 3),
        })

    # Sort: volume DESC, avg_rating ASC (more critical = lower rating), alphabetical
    summaries.sort(key=lambda x: (-x["review_count"], x["avg_rating"], x["theme"]))
    summaries = summaries[:max_themes]

    for rank, s in enumerate(summaries, start=1):
        s["rank"] = rank

    log(run_id, "classify", "rank_themes_complete",
        themes_found=len(summaries),
        top_theme=summaries[0]["theme"] if summaries else None)

    return summaries


def select_top_themes(ranked_themes: list[dict], n: int = 3) -> list[str]:
    """Return top n theme labels; if fewer than n exist, return all (EC-18)."""
    return [t["theme"] for t in ranked_themes[:n]]
