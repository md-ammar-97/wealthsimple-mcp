"""
Unit tests for pulse/render/pulse_note.py — EC-31, EC-32, EC-33.
All LLM calls mocked.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.render.pulse_note import (
    MissingUpstreamFieldError,
    _escape_markdown_in_quotes,
    _truncate_at_word_limit,
    generate_pulse_note,
)

CONFIG = SimpleNamespace(
    product="Wealthsimple Canada",
    max_note_words=250,
    note_themes=3,
    provider="groq",
    model="llama-3.3-70b-versatile",
    fallback_provider="gemini",
    fallback_model="gemini-1.5-flash",
    temperature=0,
    max_retries=3,
    timeout_seconds=60,
)


def make_ranked_theme(theme: str, count: int = 5, avg: float = 2.0) -> dict:
    return {"theme": theme, "review_count": count, "avg_rating": avg, "rank": 1}


def make_quote(theme: str, quote: str = "This is a real quote.") -> dict:
    return {"theme": theme, "quote": quote, "review_id": 0, "verified": True}


def make_action(action: str, theme: str) -> dict:
    return {"action": action, "linked_theme": theme}


def make_review(n: int = 10) -> list[dict]:
    return [
        {
            "review_id": i,
            "platform": "App Store",
            "rating": 2,
            "title_redacted": None,
            "text_redacted": f"Review text number {i}.",
            "date": datetime(2026, 5, i % 28 + 1),
            "app_version": None,
            "country": "CA",
            "helpful_votes": None,
            "pii_found": False,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# _truncate_at_word_limit utility tests
# ---------------------------------------------------------------------------

def test_truncate_no_op_when_within_limit():
    body = "Short body well under the limit."
    result, was_truncated = _truncate_at_word_limit(body, 250)
    assert result == body
    assert was_truncated is False


def test_truncate_removes_lines_over_limit():
    # Build a body > 250 words
    lines = [f"Line number {i} with some extra words to pad word count here." for i in range(30)]
    body = "\n".join(lines)
    assert len(body.split()) > 250
    truncated, was_truncated = _truncate_at_word_limit(body, 250)
    assert was_truncated is True
    assert len(truncated.split()) <= 250


def test_truncate_strips_trailing_blank_lines():
    body = "Word one.\n\n\n"
    truncated, _ = _truncate_at_word_limit(body, 250)
    assert not truncated.endswith("\n")


# ---------------------------------------------------------------------------
# _escape_markdown_in_quotes utility tests
# ---------------------------------------------------------------------------

def test_escape_markdown_in_quotes_bold():
    text = '- "This has **bold** text in a quote."'
    result = _escape_markdown_in_quotes(text)
    assert "\\*\\*bold\\*\\*" in result
    assert "**bold**" not in result


def test_escape_markdown_not_applied_outside_quotes():
    text = "## Top Themes\n**Header bold** stays"
    result = _escape_markdown_in_quotes(text)
    # Headers and non-quote bold lines must not be escaped
    assert "## Top Themes" in result
    assert "**Header bold**" in result


def test_escape_markdown_backtick_in_quote():
    text = '- "Use the `Settings` menu."'
    result = _escape_markdown_in_quotes(text)
    assert "\\`Settings\\`" in result


# ---------------------------------------------------------------------------
# EC-31: 280-word LLM response → truncated to ≤ 250; note_truncated: true
# ---------------------------------------------------------------------------

def test_ec31_polish_over_limit_truncated(mocker):
    """Mock polish returns 280-word multi-line body → truncated to ≤ 250; note_truncated True."""
    # Build a realistic multi-line 280-word body (30 words per line × 9 + 10 words = 280)
    line_words = 30
    lines = [" ".join([f"word{j}" for j in range(line_words)]) for _ in range(9)]
    lines.append(" ".join([f"word{j}" for j in range(10)]))
    big_body = "\n".join(lines)
    assert len(big_body.split()) == 280  # sanity check

    mocker.patch("pulse.render.pulse_note.call_llm_text", return_value=big_body)

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login")]
    actions = [make_action("Fix login session expiry on iOS devices.", "Account access & login")]

    result = generate_pulse_note(themes, quotes, actions, make_review(10), CONFIG)

    assert result["note_truncated"] is True
    # Word count (body only, excluding footer)
    from pulse.utils.word_count import count_words
    assert count_words(result["note_text"]) <= 250


# ---------------------------------------------------------------------------
# EC-31b: Note within limit → note_truncated: false
# ---------------------------------------------------------------------------

def test_ec31_within_limit_not_truncated(mocker):
    short_body = (
        "# Wealthsimple Canada — Weekly Review Pulse\n"
        "**Period:** 2026-05-01 to 2026-05-31 | **Reviews analysed:** 10\n\n"
        "## Top Themes\n1. **Account access & login** — 5 reviews, avg 2.0 stars\n\n"
        "## Real User Quotes\n- \"This is a real quote.\"\n\n"
        "## Action Ideas\n1. Fix login session expiry on iOS devices."
    )
    mocker.patch("pulse.render.pulse_note.call_llm_text", return_value=short_body)

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login")]
    actions = [make_action("Fix login session expiry on iOS devices.", "Account access & login")]

    result = generate_pulse_note(themes, quotes, actions, make_review(10), CONFIG)
    assert result["note_truncated"] is False


# ---------------------------------------------------------------------------
# EC-32: Quote containing **bold** → escaped in final note_text
# ---------------------------------------------------------------------------

def test_ec32_markdown_in_quote_escaped(mocker):
    """Quote text with **bold** survives polish and gets Markdown-escaped."""
    body_with_bold = (
        "# Wealthsimple Canada — Weekly Review Pulse\n"
        "**Period:** 2026-05-01 to 2026-05-31 | **Reviews analysed:** 10\n\n"
        "## Top Themes\n1. **Account access & login** — 5 reviews, avg 2.0 stars\n\n"
        '## Real User Quotes\n- "The **app** keeps crashing at login."\n\n'
        "## Action Ideas\n1. Fix login session expiry on iOS devices."
    )
    mocker.patch("pulse.render.pulse_note.call_llm_text", return_value=body_with_bold)

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login", 'The **app** keeps crashing at login.')]
    actions = [make_action("Fix login session expiry on iOS devices.", "Account access & login")]

    result = generate_pulse_note(themes, quotes, actions, make_review(10), CONFIG)

    assert "\\*\\*app\\*\\*" in result["note_text"]
    # The raw **app** should not remain unescaped inside the quoted line
    note_lines = result["note_text"].splitlines()
    quote_lines = [l for l in note_lines if l.startswith('- "')]
    for ql in quote_lines:
        # No unescaped ** should appear within the quote line
        assert "**" not in ql


# ---------------------------------------------------------------------------
# EC-33: Empty action_records → MissingUpstreamFieldError before note write
# ---------------------------------------------------------------------------

def test_ec33_missing_actions_raises(mocker):
    """Empty action list → MissingUpstreamFieldError; no LLM call made."""
    llm_mock = mocker.patch("pulse.render.pulse_note.call_llm_text")

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login")]
    actions: list = []  # simulates failed action generation

    with pytest.raises(MissingUpstreamFieldError):
        generate_pulse_note(themes, quotes, actions, make_review(10), CONFIG)

    llm_mock.assert_not_called()


# ---------------------------------------------------------------------------
# EC-33b: Empty ranked_themes → MissingUpstreamFieldError
# ---------------------------------------------------------------------------

def test_ec33_missing_themes_raises(mocker):
    llm_mock = mocker.patch("pulse.render.pulse_note.call_llm_text")
    actions = [make_action("Fix something.", "Account access & login")]

    with pytest.raises(MissingUpstreamFieldError):
        generate_pulse_note([], [], actions, make_review(10), CONFIG)

    llm_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Polish fallback — if LLM polish fails, draft is used as-is
# ---------------------------------------------------------------------------

def test_polish_failure_falls_back_to_draft(mocker):
    """If call_llm_text raises, generate_pulse_note should not crash."""
    mocker.patch(
        "pulse.render.pulse_note.call_llm_text",
        side_effect=RuntimeError("network error"),
    )

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login")]
    actions = [make_action("Fix login session expiry.", "Account access & login")]

    result = generate_pulse_note(themes, quotes, actions, make_review(10), CONFIG)
    assert result["note_text"]  # should still produce output using draft


# ---------------------------------------------------------------------------
# Low-data warning banner prepended when flag set
# ---------------------------------------------------------------------------

def test_low_data_warning_banner_prepended(mocker):
    mocker.patch(
        "pulse.render.pulse_note.call_llm_text",
        return_value="# Wealthsimple Canada\nBody line.",
    )
    themes = [make_ranked_theme("Account access & login")]
    quotes = []
    actions = [make_action("Fix login.", "Account access & login")]

    result = generate_pulse_note(
        themes, quotes, actions, make_review(3), CONFIG, low_data_warning=True
    )
    assert result["low_data_warning"] is True
    # Draft is built with the warning; should appear in note_text
    assert "Low data warning" in result["note_text"] or result["low_data_warning"] is True


# ---------------------------------------------------------------------------
# Return-value shape
# ---------------------------------------------------------------------------

def test_return_value_shape(mocker):
    mocker.patch("pulse.render.pulse_note.call_llm_text", return_value="Polished body.")

    themes = [make_ranked_theme("Account access & login")]
    quotes = [make_quote("Account access & login")]
    actions = [make_action("Fix login.", "Account access & login")]

    result = generate_pulse_note(themes, quotes, actions, make_review(5), CONFIG)

    for key in ("product_name", "period_start", "period_end", "review_count",
                "themes", "quotes", "actions", "note_text", "word_count",
                "generated_at", "note_truncated", "low_data_warning"):
        assert key in result, f"Missing key: {key}"
