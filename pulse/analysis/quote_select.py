from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pulse.utils.llm import call_llm, JSONParseError, SafetyRefusalError
from pulse.utils.logging import log

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
MIN_QUOTE_WORDS = 5
MAX_CANDIDATES = 20


def _load_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def verify_quote(quote: str, text_redacted: str) -> bool:
    """Confirm quote is a verbatim substring of text_redacted (EC-24)."""
    q = _normalise_whitespace(quote)
    t = _normalise_whitespace(text_redacted)
    return bool(q) and q in t


def _fallback_quote(candidates: list[dict], run_id: str, theme: str) -> Optional[dict]:
    """
    Fallback chain (EC-25, EC-27):
    1. Highest helpful_votes
    2. Lowest rating
    3. Most recent date
    4. None (omit — never invent)
    """
    if not candidates:
        log(run_id, "quote_select", "no_candidates", theme=theme)
        return None

    # Filter out short reviews (< MIN_QUOTE_WORDS words)
    usable = [c for c in candidates if len(c.get("text_redacted", "").split()) >= MIN_QUOTE_WORDS]
    if not usable:
        usable = candidates

    # 1. helpful_votes
    with_votes = [c for c in usable if c.get("helpful_votes") is not None]
    if with_votes:
        best = max(with_votes, key=lambda c: c["helpful_votes"])
        log(run_id, "quote_select", "fallback_used",
            theme=theme, reason="highest_helpful_votes",
            review_id=best.get("review_id"))
        return best

    # 2. lowest rating
    log(run_id, "quote_select", "fallback_used",
        theme=theme, reason="lowest_rating_no_helpful_votes")
    best = min(usable, key=lambda c: (c.get("rating", 5), -c.get("review_id", 0)))
    return best


def _build_quote_prompt(theme: str, candidates: list[dict]) -> str:
    system_prompt = _load_prompt("select_quotes.txt").replace("{theme}", theme)
    lines = []
    for i, r in enumerate(candidates):
        text = r.get("text_redacted", "")
        lines.append(f"Review {i}: <review_text>{text}</review_text>")
    prompt = "\n".join(lines)
    return system_prompt, prompt


def _select_quote_for_theme(
    theme: str,
    themed_reviews: list[dict],
    config: Any,
    run_id: str,
    strict: bool = False,
) -> Optional[dict]:
    """
    For a given theme, select one verified verbatim quote.
    Returns a QuoteRecord dict or None if no valid quote can be found.
    """
    candidates = [
        r for r in themed_reviews
        if r["theme"] == theme and len(r.get("text_redacted", "").strip()) >= 5
    ]

    if not candidates:
        log(run_id, "quote_select", "all_candidates_redacted", theme=theme)
        return None

    # Sort: deprioritise short reviews (< MIN_QUOTE_WORDS words) to the end (EC-21)
    candidates.sort(
        key=lambda c: (
            0 if len(c.get("text_redacted", "").split()) >= MIN_QUOTE_WORDS else 1,
            -(c.get("helpful_votes") or 0),
        )
    )
    candidates = candidates[:MAX_CANDIDATES]

    system_prompt, prompt = _build_quote_prompt(theme, candidates)

    try:
        result = call_llm(prompt, system_prompt, config)
        if isinstance(result, list):
            result = result[0] if result else {}
        raw_quote = result.get("quote", "")
        review_index = result.get("review_index")

        if review_index is None or not (0 <= review_index < len(candidates)):
            raise ValueError(f"review_index {review_index} out of range")

        source_review = candidates[review_index]
        verified = verify_quote(raw_quote, source_review.get("text_redacted", ""))

        if verified:
            return {
                "theme": theme,
                "quote": raw_quote,
                "review_id": source_review.get("review_id"),
                "verified": True,
            }

        # First retry failed — try strict prompt
        if not strict:
            log(run_id, "quote_select", "quote_verification_failed_retrying",
                theme=theme, review_index=review_index)
            return _select_quote_for_theme(theme, themed_reviews, config, run_id, strict=True)

        # Both attempts failed — use fallback
        log(run_id, "quote_select", "quote_verification_failed_using_fallback", theme=theme)

    except (JSONParseError, SafetyRefusalError, Exception) as exc:
        log(run_id, "quote_select", "llm_error", theme=theme, error=str(exc))

    fallback_review = _fallback_quote(candidates, run_id, theme)
    if fallback_review is None:
        return None

    fallback_text = fallback_review.get("text_redacted", "")
    # Use up to first 200 chars as the fallback quote, stopping at a sentence boundary
    quote = fallback_text[:200]
    for punct in (". ", "! ", "? "):
        idx = quote.find(punct)
        if idx > 0:
            quote = quote[:idx + 1]
            break

    return {
        "theme": theme,
        "quote": quote.strip(),
        "review_id": fallback_review.get("review_id"),
        "verified": False,
    }


def select_quotes(
    themed_reviews: list[dict],
    top_themes: list[str],
    config: Any,
    run_id: str = "dry-run",
) -> list[dict]:
    """
    Select one verified verbatim quote per top theme.
    Returns list of QuoteRecord dicts.
    """
    quote_records: list[dict] = []

    for theme in top_themes:
        record = _select_quote_for_theme(theme, themed_reviews, config, run_id)
        if record is not None:
            quote_records.append(record)
            log(run_id, "quote_select", "quote_selected",
                theme=theme,
                review_id=record.get("review_id"),
                verified=record.get("verified"))
        else:
            log(run_id, "quote_select", "quote_omitted", theme=theme)

    log(run_id, "quote_select", "quote_select_complete",
        themes_requested=len(top_themes),
        quotes_found=len(quote_records))

    return quote_records
