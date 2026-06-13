"""
Unit tests for pulse/analysis/classify.py — EC-16 to EC-22 (mocked LLM).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.analysis.classify import (
    classify_reviews,
    rank_themes,
    select_top_themes,
    THEME_LABELS,
)

CONFIG = SimpleNamespace(
    batch_size=50,
    max_review_chars=2000,
    max_themes=5,
    max_retries=3,
    temperature=0,
    provider="groq",
    model="llama-3.3-70b-versatile",
    fallback_provider="gemini",
    fallback_model="gemini-1.5-flash",
    timeout_seconds=60,
)


def make_review(review_id: int, text: str, rating: int = 3, platform: str = "App Store"):
    return {
        "review_id": review_id,
        "platform": platform,
        "rating": rating,
        "title_redacted": None,
        "text_redacted": text,
        "date": datetime(2026, 5, 15),
        "app_version": None,
        "country": "CA",
        "helpful_votes": None,
        "pii_found": False,
    }


def mock_classify_response(reviews, theme="App performance, bugs & reliability", confidence=0.9):
    return [
        {"review_index": i, "theme": theme, "confidence": confidence}
        for i in range(len(reviews))
    ]


# ---------------------------------------------------------------------------
# EC-16: Review mentioning multiple topics → single theme returned
# ---------------------------------------------------------------------------
def test_ec16_single_theme_returned(mocker):
    reviews = [make_review(0, "Can't log in and also the crypto section is missing my transaction history.")]
    mock = mocker.patch("pulse.analysis.classify.call_llm")
    mock.return_value = [{"review_index": 0, "theme": "Account access & login", "confidence": 0.8}]

    result = classify_reviews(reviews, CONFIG)
    assert len(result) == 1
    assert result[0]["theme"] == "Account access & login"


# ---------------------------------------------------------------------------
# EC-17: All reviews → one theme in ranked output
# ---------------------------------------------------------------------------
def test_ec17_all_one_theme(mocker):
    reviews = [
        make_review(i, f"The app crashes constantly and I cannot use it. Issue {i}.", rating=1)
        for i in range(10)
    ]
    mock = mocker.patch("pulse.analysis.classify.call_llm")
    mock.return_value = mock_classify_response(reviews, "App performance, bugs & reliability")

    themed = classify_reviews(reviews, CONFIG)
    ranked = rank_themes(themed, CONFIG)
    assert len(ranked) == 1
    assert ranked[0]["theme"] == "App performance, bugs & reliability"


# ---------------------------------------------------------------------------
# EC-18: 2 distinct themes → select_top_themes(n=3) returns 2
# ---------------------------------------------------------------------------
def test_ec18_fewer_than_3_themes(mocker):
    reviews = [
        make_review(0, "Login keeps failing every time I open the app.", rating=1),
        make_review(1, "The app crashes every single time I use it.", rating=1),
    ]
    mock = mocker.patch("pulse.analysis.classify.call_llm")
    mock.return_value = [
        {"review_index": 0, "theme": "Account access & login", "confidence": 0.9},
        {"review_index": 1, "theme": "App performance, bugs & reliability", "confidence": 0.85},
    ]

    themed = classify_reviews(reviews, CONFIG)
    ranked = rank_themes(themed, CONFIG)
    top = select_top_themes(ranked, n=3)
    assert len(top) == 2


# ---------------------------------------------------------------------------
# EC-19: Invalid theme label → string-similarity fallback to valid label
# ---------------------------------------------------------------------------
def test_ec19_invalid_theme_fallback(mocker):
    reviews = [make_review(0, "The app is great but fees are confusing and unclear.")]
    mock = mocker.patch("pulse.analysis.classify.call_llm")
    # Return invalid label — should be corrected by _closest_theme
    mock.return_value = [{"review_index": 0, "theme": "General feedback", "confidence": 0.5}]

    result = classify_reviews(reviews, CONFIG)
    assert len(result) == 1
    assert result[0]["theme"] in THEME_LABELS


# ---------------------------------------------------------------------------
# EC-20: Missing indices in LLM response → re-queued
# ---------------------------------------------------------------------------
def test_ec20_missing_indices_requeued(mocker):
    reviews = [make_review(i, f"Review text for testing purposes number {i} is valid.", rating=3)
               for i in range(5)]

    call_count = {"n": 0}

    def side_effect(prompt, system_prompt, config):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Return only 3 of 5 reviews (batch-relative indices 0, 1, 2 — missing 3, 4)
            return [
                {"review_index": 0, "theme": "App performance, bugs & reliability", "confidence": 0.9},
                {"review_index": 1, "theme": "Account access & login", "confidence": 0.85},
                {"review_index": 2, "theme": "Transfers, deposits & withdrawals", "confidence": 0.8},
            ]
        # Second call: re-queued batch has 2 reviews (batch-relative 0 and 1)
        return [
            {"review_index": 0, "theme": "Customer support & issue resolution", "confidence": 0.7},
            {"review_index": 1, "theme": "Fees, pricing & product communication", "confidence": 0.75},
        ]

    mocker.patch("pulse.analysis.classify.call_llm", side_effect=side_effect)

    result = classify_reviews(reviews, CONFIG)
    assert len(result) == 5
    assert call_count["n"] >= 2


# ---------------------------------------------------------------------------
# EC-21: One-word / short reviews classified; deprioritised for quotes
# ---------------------------------------------------------------------------
def test_ec21_short_reviews_classified(mocker):
    reviews = [
        make_review(0, "Great"),
        make_review(1, "Terrible app"),
        make_review(2, "Love it"),
    ]
    mock = mocker.patch("pulse.analysis.classify.call_llm")
    mock.return_value = [
        {"review_index": 0, "theme": "App performance, bugs & reliability", "confidence": 0.4},
        {"review_index": 1, "theme": "App performance, bugs & reliability", "confidence": 0.6},
        {"review_index": 2, "theme": "App performance, bugs & reliability", "confidence": 0.4},
    ]

    result = classify_reviews(reviews, CONFIG)
    assert len(result) == 3
    for r in result:
        assert r["theme"] in THEME_LABELS


# ---------------------------------------------------------------------------
# EC-22: Tie in volume → lower avg rating wins; deterministic across runs
# ---------------------------------------------------------------------------
def test_ec22_tiebreak_by_avg_rating_deterministic():
    # 15 reviews per theme A and B, but B has lower avg rating (more critical)
    theme_a = [
        {**make_review(i, f"Login issue {i}", rating=3), "theme": "Account access & login", "confidence": 0.9}
        for i in range(15)
    ]
    theme_b = [
        {**make_review(i + 15, f"App crash {i}", rating=1), "theme": "App performance, bugs & reliability", "confidence": 0.9}
        for i in range(15)
    ]
    themed = theme_a + theme_b

    results = []
    for _ in range(3):
        ranked = rank_themes(themed, CONFIG)
        results.append(ranked[0]["theme"])

    # All 3 runs should return the same winner (lower avg rating = more critical)
    assert len(set(results)) == 1
    # "App performance, bugs & reliability" has avg_rating=1, which is lower → wins
    assert results[0] == "App performance, bugs & reliability"


# ---------------------------------------------------------------------------
# Theme rank ordering test
# ---------------------------------------------------------------------------
def test_rank_themes_ordering():
    themed = (
        [{**make_review(i, f"Text {i}", rating=2), "theme": "Customer support & issue resolution", "confidence": 0.9}
         for i in range(5)] +
        [{**make_review(i + 5, f"Text {i}", rating=1), "theme": "App performance, bugs & reliability", "confidence": 0.9}
         for i in range(10)]
    )
    ranked = rank_themes(themed, CONFIG)
    assert ranked[0]["theme"] == "App performance, bugs & reliability"
    assert ranked[0]["review_count"] == 10
    assert ranked[1]["review_count"] == 5


# ---------------------------------------------------------------------------
# select_top_themes returns at most n
# ---------------------------------------------------------------------------
def test_select_top_themes_caps_at_n():
    ranked = [{"theme": t, "review_count": 5, "avg_rating": 2.0, "rank": i + 1}
              for i, t in enumerate(THEME_LABELS[:5])]
    top = select_top_themes(ranked, n=3)
    assert len(top) == 3
    assert top == [t["theme"] for t in ranked[:3]]
