"""
Unit tests for pulse/render/email_draft.py — EC-34, EC-35.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.render.email_draft import _strip_markdown, render_email_draft

CONFIG = SimpleNamespace(
    product="Wealthsimple Canada",
    email_recipient="team@wealthsimple.com",
    sender_name="Pulse Pipeline",
    delivery_mode="local",
)

CONFIG_NO_RECIPIENT = SimpleNamespace(
    product="Wealthsimple Canada",
    email_recipient="",
    sender_name="Pulse Pipeline",
    delivery_mode="local",
)

SAMPLE_NOTE = """\
# Wealthsimple Canada — Weekly Review Pulse
**Period:** 2026-05-01 to 2026-05-31 | **Reviews analysed:** 49

## Top Themes
1. **Account access & login** — 12 reviews, avg 1.8 stars
2. **App performance, bugs & reliability** — 10 reviews, avg 2.1 stars

## Real User Quotes
- "Cannot log in to my account for several days."
- "The app crashes every time I open my portfolio."

## Action Ideas
1. Fix session expiry affecting iOS users.
2. Investigate crash in portfolio view on iOS 17.

---
*Generated: 2026-06-08 10:00 UTC | Word count: 72*
"""


# ---------------------------------------------------------------------------
# _strip_markdown utility tests
# ---------------------------------------------------------------------------

def test_strip_removes_hash_headers():
    result = _strip_markdown("## Top Themes")
    assert "#" not in result
    assert "Top Themes" in result


def test_strip_removes_single_hash():
    result = _strip_markdown("# Title")
    assert "#" not in result
    assert "Title" in result


def test_strip_removes_bold():
    result = _strip_markdown("This is **bold** text.")
    assert "**" not in result
    assert "bold" in result


def test_strip_removes_italic():
    result = _strip_markdown("This is *italic* text.")
    assert result.count("*") == 0
    assert "italic" in result


def test_strip_converts_list_marker():
    result = _strip_markdown("- First item")
    assert "• First item" in result
    assert result.strip().startswith("•")


def test_strip_converts_divider():
    result = _strip_markdown("---")
    assert result.strip() == ""


def test_strip_removes_backtick_code():
    result = _strip_markdown("Use `Settings` to configure.")
    assert "`" not in result
    assert "Settings" in result


# ---------------------------------------------------------------------------
# EC-34: Missing email_recipient → placeholder written; no abort
# ---------------------------------------------------------------------------

def test_ec34_missing_recipient_uses_placeholder():
    """email_recipient absent → placeholder used; function returns without raising."""
    result = render_email_draft(SAMPLE_NOTE, CONFIG_NO_RECIPIENT)
    assert "To: " in result
    # Should use the placeholder, not crash
    assert "@" in result.split("\n")[0]


def test_ec34_present_recipient_used():
    result = render_email_draft(SAMPLE_NOTE, CONFIG)
    assert "To: team@wealthsimple.com" in result


# ---------------------------------------------------------------------------
# EC-35: Markdown stripped — no # or * in .txt output
# ---------------------------------------------------------------------------

def test_ec35_no_markdown_in_email(capfd):
    result = render_email_draft(SAMPLE_NOTE, CONFIG)

    # Split off the header lines (To:, Subject:) before scanning body
    body_start = result.find("\nHi Team,")
    body = result[body_start:]

    # The email body must not contain raw Markdown
    for line in body.splitlines():
        # No bare ## or # heading markers
        assert not line.startswith("#"), f"Found Markdown heading: {line!r}"
        # No **bold** patterns
        assert "**" not in line, f"Found bold Markdown: {line!r}"


def test_ec35_no_hash_character_in_body():
    result = render_email_draft(SAMPLE_NOTE, CONFIG)
    body_start = result.find("\nHi Team,")
    body = result[body_start:]
    assert "#" not in body


def test_ec35_bullet_points_converted():
    result = render_email_draft(SAMPLE_NOTE, CONFIG)
    # Original "- " list markers should become "• "
    assert "• " in result
    # And no raw "- " bullet lines remain (only "---" divider lines, already stripped)
    body_start = result.find("\nHi Team,")
    body = result[body_start:]
    for line in body.splitlines():
        # No lines starting with "- " (list markers should all be converted)
        assert not line.startswith("- "), f"Found unconverted list marker: {line!r}"


# ---------------------------------------------------------------------------
# Email structure tests
# ---------------------------------------------------------------------------

def test_email_has_expected_sections():
    result = render_email_draft(SAMPLE_NOTE, CONFIG)
    assert result.startswith("To: ")
    assert "Subject: Weekly Review Pulse — Wealthsimple Canada" in result
    assert "Hi Team," in result
    assert "Thanks," in result
    assert "Pulse Pipeline" in result


def test_email_contains_note_content():
    result = render_email_draft(SAMPLE_NOTE, CONFIG)
    # Theme name should appear (stripped of **bold** markers)
    assert "Account access & login" in result
    # Quote text should appear
    assert "Cannot log in" in result
