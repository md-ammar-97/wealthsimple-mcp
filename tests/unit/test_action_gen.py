"""
Unit tests for pulse/analysis/action_gen.py — EC-28 to EC-30 (mocked LLM).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.analysis.action_gen import generate_actions, _trim_at_sentence_boundary
from pulse.analysis.classify import THEME_LABELS

CONFIG = SimpleNamespace(
    batch_size=50,
    max_review_chars=2000,
    max_action_chars=200,
    max_retries=3,
    temperature=0,
    provider="groq",
    model="llama-3.3-70b-versatile",
    fallback_provider="gemini",
    fallback_model="gemini-1.5-flash",
    timeout_seconds=60,
)


def make_quote(theme: str, quote: str = "Sample quote text for this theme."):
    return {"theme": theme, "quote": quote, "review_id": 0, "verified": True}


# ---------------------------------------------------------------------------
# EC-28: Login + onboarding → 3 distinct actions
# ---------------------------------------------------------------------------
def test_ec28_distinct_actions_for_related_themes(mocker):
    top_themes = [
        "Account access & login",
        "Onboarding & verification",
        "App performance, bugs & reliability",
    ]
    quotes = [make_quote(t) for t in top_themes]

    mock = mocker.patch("pulse.analysis.action_gen.call_llm")
    mock.return_value = [
        {"action": "Investigate session expiry affecting iOS users and fix token refresh timing.",
         "linked_theme": "Account access & login"},
        {"action": "Streamline identity verification to reduce completion time from weeks to hours.",
         "linked_theme": "Onboarding & verification"},
        {"action": "Fix crash loop in portfolio view triggered by iOS 17 background state changes.",
         "linked_theme": "App performance, bugs & reliability"},
    ]

    result = generate_actions(top_themes, quotes, CONFIG)
    assert len(result) == 3
    action_texts = [r["action"] for r in result]
    # All actions must be distinct
    assert len(set(action_texts)) == 3
    # All linked themes must be in the top 3
    for r in result:
        assert r["linked_theme"] in top_themes


# ---------------------------------------------------------------------------
# EC-29: All positive reviews → amplification framing (no fabricated problems)
# ---------------------------------------------------------------------------
def test_ec29_positive_reviews_amplification(mocker):
    top_themes = [
        "Trading, investing & crypto",
        "App performance, bugs & reliability",
        "Transfers, deposits & withdrawals",
    ]
    quotes = [
        make_quote("Trading, investing & crypto", "The robo-advisor is excellent and saves me time."),
        make_quote("App performance, bugs & reliability", "The app loads quickly and never crashes."),
        make_quote("Transfers, deposits & withdrawals", "Transfers are always fast and reliable."),
    ]

    mock = mocker.patch("pulse.analysis.action_gen.call_llm")
    mock.return_value = [
        {"action": "Build on the robo-advisor by adding personalised portfolio insights to deepen engagement.",
         "linked_theme": "Trading, investing & crypto"},
        {"action": "Extend the fast load performance to the new tax documents section as it rolls out.",
         "linked_theme": "App performance, bugs & reliability"},
        {"action": "Promote same-day transfer speed as a differentiator in onboarding communications.",
         "linked_theme": "Transfers, deposits & withdrawals"},
    ]

    result = generate_actions(top_themes, quotes, CONFIG)
    assert len(result) == 3
    # No action should imply fabricated problems (basic keyword check)
    for r in result:
        text_lower = r["action"].lower()
        assert "fix" not in text_lower or "bug" not in text_lower


# ---------------------------------------------------------------------------
# EC-30: 350-char action → trimmed at sentence boundary; grammatically complete
# ---------------------------------------------------------------------------
def test_ec30_action_trimmed_at_sentence_boundary(mocker):
    top_themes = ["Account access & login"]
    quotes = [make_quote("Account access & login")]

    long_action = (
        "Investigate the persistent session expiry issue that is affecting thousands of iOS users. "
        "Work with the authentication team to fix the token refresh mechanism. "
        "This will reduce login failures significantly and improve user retention metrics."
    )
    assert len(long_action) > 200

    mock = mocker.patch("pulse.analysis.action_gen.call_llm")
    mock.return_value = [
        {"action": long_action, "linked_theme": "Account access & login"}
    ]

    result = generate_actions(top_themes, quotes, CONFIG)
    assert len(result) == 1
    assert len(result[0]["action"]) <= 200
    # Must end with a sentence-terminating character
    assert result[0]["action"].rstrip()[-1] in (".", "!", "?", "")


# ---------------------------------------------------------------------------
# _trim_at_sentence_boundary utility tests
# ---------------------------------------------------------------------------
def test_trim_at_sentence_boundary_no_trim_needed():
    text = "Short action under 200 chars."
    assert _trim_at_sentence_boundary(text, 200) == text


def test_trim_at_sentence_boundary_trims_at_period():
    text = "Fix the login bug. This extra sentence pushes it over two hundred characters of total length in this action."
    result = _trim_at_sentence_boundary(text, 50)
    assert len(result) <= 50
    assert result.endswith(".")


def test_trim_at_sentence_boundary_no_sentence_marker():
    text = "A very long action with no sentence boundary that keeps going and going and going and going here"
    result = _trim_at_sentence_boundary(text, 50)
    assert len(result) <= 50


# ---------------------------------------------------------------------------
# linked_theme validation — must stay within top themes
# ---------------------------------------------------------------------------
def test_linked_theme_must_be_in_top_themes(mocker):
    top_themes = ["Account access & login", "Onboarding & verification"]
    quotes = [make_quote(t) for t in top_themes]

    mock = mocker.patch("pulse.analysis.action_gen.call_llm")
    mock.return_value = [
        {"action": "Fix login session expiry on iOS devices to reduce auth failures.",
         "linked_theme": "Tax, statements & documents"},  # not in top themes
        {"action": "Speed up identity verification steps to improve user activation rate.",
         "linked_theme": "Onboarding & verification"},
    ]

    result = generate_actions(top_themes, quotes, CONFIG)
    for r in result:
        assert r["linked_theme"] in top_themes


# ---------------------------------------------------------------------------
# EC-18 variant: fewer than 3 themes → generates matching count
# ---------------------------------------------------------------------------
def test_action_count_matches_theme_count(mocker):
    top_themes = ["Account access & login", "Onboarding & verification"]
    quotes = [make_quote(t) for t in top_themes]

    mock = mocker.patch("pulse.analysis.action_gen.call_llm")
    mock.return_value = [
        {"action": "Fix session expiry affecting iOS users to reduce authentication failures.",
         "linked_theme": "Account access & login"},
        {"action": "Streamline identity verification to reduce wait time from days to hours.",
         "linked_theme": "Onboarding & verification"},
    ]

    result = generate_actions(top_themes, quotes, CONFIG)
    assert len(result) == 2
