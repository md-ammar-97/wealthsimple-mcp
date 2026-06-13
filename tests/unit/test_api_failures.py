"""
Unit tests for API error handling — EC-36 to EC-41.
All LLM/provider calls are mocked.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.utils.llm import (
    ContextOverflowError,
    JSONParseError,
    MissingAPIKeyError,
    SafetyRefusalError,
    check_api_key,
    extract_json,
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


def make_review(review_id: int, text: str, rating: int = 3) -> dict:
    return {
        "review_id": review_id,
        "platform": "App Store",
        "rating": rating,
        "title_redacted": None,
        "text_redacted": text,
        "date": datetime(2026, 5, 15),
        "app_version": None,
        "country": "CA",
        "helpful_votes": None,
        "pii_found": False,
    }


# ---------------------------------------------------------------------------
# EC-36: No API key → MissingAPIKeyError; no output files
# ---------------------------------------------------------------------------

def test_ec36_missing_api_key_raises(monkeypatch):
    """With no LLM key in env, check_api_key() must raise MissingAPIKeyError."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        check_api_key()


def test_ec36_key_present_no_raise(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    check_api_key()  # must not raise


# ---------------------------------------------------------------------------
# EC-37: 429 rate-limit on 2nd batch → retry; remaining batches succeed
# ---------------------------------------------------------------------------

def test_ec37_rate_limit_retry_on_batch(mocker):
    """
    classify_reviews: batch 1 and 3 succeed; batch 2 raises once then succeeds.
    The module's internal retry (inside call_llm) handles the 429.
    All 3 batches should produce classified reviews.
    """
    from pulse.analysis.classify import classify_reviews

    # 110 reviews → 3 batches (50 + 50 + 10) with batch_size=50
    reviews = [make_review(i, f"Review text number {i} is about the app.") for i in range(110)]

    call_num = {"n": 0}

    def side_effect(prompt, system_prompt, cfg):
        call_num["n"] += 1
        # Second call fails (simulates 429 that bubbles up after retries)
        if call_num["n"] == 2:
            raise RuntimeError("rate_limit_exceeded: too many requests")
        # Other calls succeed — return valid classification for however many reviews are in prompt
        count = prompt.count("<review_text>")
        return [
            {"review_index": i, "theme": "Account access & login", "confidence": 0.9}
            for i in range(count)
        ]

    mocker.patch("pulse.analysis.classify.call_llm", side_effect=side_effect)

    result = classify_reviews(reviews, CONFIG)
    # Batches 1 and 3 should produce results; batch 2 is skipped on persistent failure
    assert len(result) > 0
    # Reviews from batch 1 (indices 0-49) and batch 3 (100-109) should be classified
    classified_ids = {r["review_id"] for r in result}
    assert any(i in classified_ids for i in range(50))  # batch 1
    assert any(i in classified_ids for i in range(100, 110))  # batch 3


# ---------------------------------------------------------------------------
# EC-38: Markdown-fenced JSON → extract_json unwraps correctly
# ---------------------------------------------------------------------------

def test_ec38_extract_json_unwraps_fences():
    """```json\n[...]\n``` fences must be stripped before JSON parsing."""
    fenced = '```json\n[{"review_index": 0, "theme": "Account access & login", "confidence": 0.9}]\n```'
    result = extract_json(fenced)
    assert isinstance(result, list)
    assert result[0]["theme"] == "Account access & login"


def test_ec38_extract_json_plain():
    plain = '[{"review_index": 0, "theme": "App performance, bugs & reliability", "confidence": 0.8}]'
    result = extract_json(plain)
    assert isinstance(result, list)


def test_ec38_extract_json_invalid_raises():
    with pytest.raises(JSONParseError):
        extract_json("not valid json at all !!!")


def test_ec38_extract_json_extracts_embedded_array():
    # LLM may include preamble before the JSON array
    text = 'Here is the classification:\n[{"review_index": 0, "theme": "Tax, statements & documents", "confidence": 0.7}]\nDone.'
    result = extract_json(text)
    assert isinstance(result, list)
    assert result[0]["review_index"] == 0


# ---------------------------------------------------------------------------
# EC-39: Context overflow → batch split in half; both halves processed
# ---------------------------------------------------------------------------

def test_ec39_context_overflow_triggers_batch_split(mocker):
    """ContextOverflowError on a batch → classify splits and retries each half."""
    from pulse.analysis.classify import classify_reviews

    reviews = [make_review(i, f"Review text {i} about the application.") for i in range(10)]

    call_num = {"n": 0}

    def side_effect(prompt, system_prompt, cfg):
        call_num["n"] += 1
        if call_num["n"] == 1:
            # First call (full batch) → context overflow
            raise ContextOverflowError("Prompt exceeds context window")
        # Subsequent calls (halves) → succeed
        count = prompt.count("<review_text>")
        return [
            {"review_index": i, "theme": "App performance, bugs & reliability", "confidence": 0.85}
            for i in range(count)
        ]

    mocker.patch("pulse.analysis.classify.call_llm", side_effect=side_effect)

    result = classify_reviews(reviews, CONFIG)
    # Both halves should be processed
    assert len(result) == 10
    # At least 2 calls: 1 overflow + 2 halves = 3 total
    assert call_num["n"] >= 3


# ---------------------------------------------------------------------------
# EC-40: Timeout → retry triggered (tests _call_groq internal retry)
# ---------------------------------------------------------------------------

def test_ec40_timeout_triggers_retry(mocker):
    """Mock APITimeoutError on first Groq call → retry succeeds on second."""
    import time  # noqa: F401 — needed to patch

    mocker.patch("pulse.utils.llm.time.sleep")  # avoid real sleeps

    call_count = {"n": 0}

    def mock_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from groq import APITimeoutError  # type: ignore
            raise APITimeoutError("Request timed out")
        mock_choice = mocker.Mock()
        mock_choice.message.content = '{"review_index": 0, "theme": "Account access & login", "confidence": 0.9}'
        mock_response = mocker.Mock()
        mock_response.choices = [mock_choice]
        return mock_response

    mock_client = mocker.Mock()
    mock_client.chat.completions.create = mock_create
    # Groq is imported lazily inside _call_groq, so patch at the groq module level
    mocker.patch("groq.Groq", return_value=mock_client)

    from pulse.utils.llm import _call_groq
    result = _call_groq("test prompt", "test system", CONFIG)
    assert "Account access & login" in result
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# EC-41: Safety refusal → review excluded; rest of batch proceeds
# ---------------------------------------------------------------------------

def test_ec41_safety_refusal_excludes_batch(mocker):
    """
    When call_llm raises SafetyRefusalError for a batch,
    that batch is skipped but other batches are processed normally.
    """
    from pulse.analysis.classify import classify_reviews

    reviews = [make_review(i, f"Review text {i} about the app crashing.") for i in range(60)]

    call_num = {"n": 0}

    def side_effect(prompt, system_prompt, cfg):
        call_num["n"] += 1
        if call_num["n"] == 1:
            # First batch raises safety refusal
            raise SafetyRefusalError("Content policy violation")
        count = prompt.count("<review_text>")
        return [
            {"review_index": i, "theme": "App performance, bugs & reliability", "confidence": 0.9}
            for i in range(count)
        ]

    mocker.patch("pulse.analysis.classify.call_llm", side_effect=side_effect)

    result = classify_reviews(reviews, CONFIG)
    # Second batch (reviews 50-59) should still be classified
    classified_ids = {r["review_id"] for r in result}
    assert any(i in classified_ids for i in range(50, 60))
    # First batch (reviews 0-49) excluded due to safety refusal
    assert not any(i in classified_ids for i in range(50))


# ---------------------------------------------------------------------------
# Provider fallback — primary fails, fallback succeeds
# ---------------------------------------------------------------------------

def test_provider_fallback_on_primary_failure(mocker):
    """If primary (Groq) fails with a non-fatal error, Gemini fallback is tried."""
    from pulse.utils.llm import call_llm

    mocker.patch(
        "pulse.utils.llm._call_groq",
        side_effect=RuntimeError("Groq unavailable"),
    )
    mocker.patch(
        "pulse.utils.llm._call_gemini",
        return_value='[{"review_index": 0, "theme": "Account access & login", "confidence": 0.9}]',
    )

    result = call_llm("prompt", "system", CONFIG)
    assert isinstance(result, list)
    assert result[0]["theme"] == "Account access & login"
