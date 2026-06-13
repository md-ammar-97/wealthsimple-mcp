"""
Unit tests for pulse/analysis/quote_select.py — EC-24 to EC-27 (mocked LLM).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.analysis.quote_select import select_quotes, verify_quote

CONFIG = SimpleNamespace(
    batch_size=50,
    max_review_chars=2000,
    max_retries=3,
    temperature=0,
    provider="groq",
    model="llama-3.3-70b-versatile",
    fallback_provider="gemini",
    fallback_model="gemini-1.5-flash",
    timeout_seconds=60,
)


def make_themed_review(review_id: int, text: str, theme: str, rating: int = 2,
                        helpful_votes=None):
    return {
        "review_id": review_id,
        "platform": "App Store",
        "rating": rating,
        "title_redacted": None,
        "text_redacted": text,
        "date": datetime(2026, 5, 15),
        "app_version": None,
        "country": "CA",
        "helpful_votes": helpful_votes,
        "pii_found": False,
        "theme": theme,
        "confidence": 0.85,
    }


THEME = "App performance, bugs & reliability"


# ---------------------------------------------------------------------------
# verify_quote utility tests
# ---------------------------------------------------------------------------
def test_verify_quote_exact_match():
    assert verify_quote("the app crashes", "The app crashes every time I open it.") is False
    assert verify_quote("app crashes", "The app crashes every time I open it.") is True


def test_verify_quote_normalises_whitespace():
    # Both sides are whitespace-normalised per spec EC-24 — extra spaces in quote still match
    assert verify_quote("app  crashes", "The app crashes.") is True
    assert verify_quote("app crashes", "The  app  crashes.") is True


def test_verify_quote_empty():
    assert verify_quote("", "Some text") is False


# ---------------------------------------------------------------------------
# EC-24: Hallucinated quote → fallback fires; no invented text in output
# ---------------------------------------------------------------------------
def test_ec24_hallucinated_quote_triggers_fallback(mocker):
    reviews = [
        make_themed_review(0, "The app crashes every time I open my portfolio.", THEME,
                           rating=1, helpful_votes=5),
        make_themed_review(1, "Very slow performance and constant freezing issues.", THEME,
                           rating=2, helpful_votes=2),
    ]
    call_count = {"n": 0}

    def side_effect(prompt, system_prompt, config):
        call_count["n"] += 1
        # Return a quote that does NOT exist in any review
        return {"quote": "This quote was completely made up by the model.", "review_index": 0}

    mocker.patch("pulse.analysis.quote_select.call_llm", side_effect=side_effect)

    result = select_quotes(reviews, [THEME], CONFIG)
    assert len(result) == 1
    # Result must be from the actual reviews — not the invented text
    actual_texts = [r["text_redacted"] for r in reviews]
    quote = result[0]["quote"]
    # The fallback quote should come from one of the real reviews
    found_in_real = any(quote in text or text.startswith(quote[:30]) for text in actual_texts)
    assert found_in_real or result[0]["verified"] is False
    # Most importantly, invented text must not be in output
    assert "This quote was completely made up" not in quote


# ---------------------------------------------------------------------------
# EC-25: All candidates fully redacted → theme shown without quote; omission logged
# ---------------------------------------------------------------------------
def test_ec25_all_candidates_fully_redacted(mocker):
    # text_redacted is too short (< 5 chars) → excluded
    reviews = [
        make_themed_review(0, "[id]", THEME),
        make_themed_review(1, "[id]", THEME),
    ]
    mock = mocker.patch("pulse.analysis.quote_select.call_llm")

    result = select_quotes(reviews, [THEME], CONFIG)
    # Should return empty list (no quote for this theme) — theme is not fabricated
    assert len(result) == 0
    mock.assert_not_called()


# ---------------------------------------------------------------------------
# EC-26: Verbatim check — returned quote must pass substring validation
# ---------------------------------------------------------------------------
def test_ec26_verbatim_check(mocker):
    real_text = "I thought the app was good, but it keeps crashing unexpectedly."
    reviews = [make_themed_review(0, real_text, THEME)]

    mock = mocker.patch("pulse.analysis.quote_select.call_llm")
    # Return the actual verbatim text
    mock.return_value = {"quote": "it keeps crashing unexpectedly", "review_index": 0}

    result = select_quotes(reviews, [THEME], CONFIG)
    assert len(result) == 1
    assert result[0]["verified"] is True
    assert "it keeps crashing unexpectedly" in result[0]["quote"]


# ---------------------------------------------------------------------------
# EC-27: No helpful_votes → fallback by lowest rating; logged
# ---------------------------------------------------------------------------
def test_ec27_no_helpful_votes_fallback_by_rating(mocker):
    reviews = [
        make_themed_review(0, "The app crashes constantly and I lose all my work.", THEME,
                           rating=1, helpful_votes=None),
        make_themed_review(1, "Performance issues affect my ability to trade effectively.", THEME,
                           rating=3, helpful_votes=None),
    ]
    call_count = {"n": 0}

    def side_effect(prompt, system_prompt, config):
        call_count["n"] += 1
        # Always return invented quote to force fallback
        return {"quote": "This was completely invented by the LLM model.", "review_index": 0}

    mocker.patch("pulse.analysis.quote_select.call_llm", side_effect=side_effect)

    result = select_quotes(reviews, [THEME], CONFIG)
    # Should fall back to lowest rating (review 0, rating=1) since no helpful_votes
    assert len(result) == 1
    assert result[0]["review_id"] == 0  # lowest rating fallback


# ---------------------------------------------------------------------------
# Multiple themes — one per top theme
# ---------------------------------------------------------------------------
def test_multiple_themes_one_quote_each(mocker):
    theme1 = "Account access & login"
    theme2 = "Transfers, deposits & withdrawals"

    reviews = [
        make_themed_review(0, "I cannot log in to my account for several days now.", theme1,
                           rating=1),
        make_themed_review(1, "My bank transfer has been pending for five business days.", theme2,
                           rating=2),
    ]

    def side_effect(prompt, system_prompt, config):
        if theme1 in system_prompt:
            return {"quote": "I cannot log in to my account for several days now.", "review_index": 0}
        return {"quote": "My bank transfer has been pending for five business days.", "review_index": 0}

    mocker.patch("pulse.analysis.quote_select.call_llm", side_effect=side_effect)

    result = select_quotes(reviews, [theme1, theme2], CONFIG)
    assert len(result) == 2
    themes_returned = {r["theme"] for r in result}
    assert theme1 in themes_returned
    assert theme2 in themes_returned
