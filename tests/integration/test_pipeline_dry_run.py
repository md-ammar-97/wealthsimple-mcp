"""
Integration tests — EC-42, EC-43, EC-44, plus full dry-run verification.
No real LLM calls are made (LLM modules mocked where needed).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.ledger.run_ledger import compute_input_hash
from pulse.orchestrator import run_pipeline

FIXTURES = Path(__file__).parent.parent / "fixtures"
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG = SimpleNamespace(
    product="Wealthsimple Canada",
    review_window_weeks=10,
    min_reviews=5,
    max_review_chars=2000,
    max_themes=5,
    note_themes=3,
    max_note_words=250,
    quotes_per_note=3,
    action_ideas=3,
    max_action_chars=200,
    provider="groq",
    model="llama-3.3-70b-versatile",
    fallback_provider="gemini",
    fallback_model="gemini-1.5-flash",
    temperature=0,
    batch_size=50,
    max_retries=3,
    timeout_seconds=60,
    ledger_backend="json",
    email_recipient="team@example.com",
    sender_name="Pulse Pipeline",
    delivery_mode="local",
    docs_mcp={"enabled": False, "doc_id": ""},
    gmail_mcp={"enabled": False, "email_mode": "draft"},
)


# ---------------------------------------------------------------------------
# Full dry-run integration: only reviews_clean.csv written; no LLM calls
# ---------------------------------------------------------------------------

def _setup_tmp_project(tmp_path: Path) -> None:
    """Copy config files into tmp_path so it acts as project root."""
    import shutil
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "data" / "runs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs").mkdir(exist_ok=True)
    shutil.copy(str(PROJECT_ROOT / "config" / "pipeline.yaml"), str(tmp_path / "config" / "pipeline.yaml"))
    shutil.copy(str(PROJECT_ROOT / "config" / "delivery.yaml"), str(tmp_path / "config" / "delivery.yaml"))


def test_dry_run_creates_only_clean_csv(tmp_path, monkeypatch):
    """
    Full dry-run should write reviews_clean.csv but NOT weekly_note.md or email_draft.txt.
    No LLM calls expected.
    """
    _setup_tmp_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    csv_path = str(FIXTURES / "sample_reviews.csv")
    output_dir = str(tmp_path / "outputs")
    clean_dir = str(tmp_path / "data" / "output")

    result = run_pipeline(
        CONFIG, csv_path,
        dry_run=True,
        output_dir=output_dir,
        clean_csv_dir=clean_dir,
    )

    assert result["status"] == "dry_run"
    assert (Path(clean_dir) / "reviews_clean.csv").exists(), "reviews_clean.csv not written"
    assert not (Path(output_dir) / "weekly_note.md").exists(), "weekly_note.md must NOT be written in dry-run"
    assert not (Path(output_dir) / "email_draft.txt").exists(), "email_draft.txt must NOT be written in dry-run"


# ---------------------------------------------------------------------------
# EC-42: Same CSV run twice → identical input_hash (deterministic)
# ---------------------------------------------------------------------------

def test_ec42_input_hash_deterministic():
    """compute_input_hash must return the same value for the same inputs."""
    csv_path = str(FIXTURES / "sample_reviews.csv")
    h1 = compute_input_hash(csv_path, "config/pipeline.yaml")
    h2 = compute_input_hash(csv_path, "config/pipeline.yaml")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_ec42_full_pipeline_deterministic(tmp_path, monkeypatch, mocker):
    """
    Two runs with identical CSV + mocked LLM → identical weekly_note.md content.
    """
    _setup_tmp_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    classify_response = [
        {"review_index": i, "theme": "Account access & login", "confidence": 0.9}
        for i in range(10)
    ]
    quote_response = {
        "quote": "Cannot log in for several days.",
        "review_index": 0,
    }
    action_response = [
        {"action": "Fix session expiry on iOS devices.", "linked_theme": "Account access & login"}
    ]
    polished_note = (
        "# Wealthsimple Canada — Weekly Review Pulse\n"
        "**Period:** 2026-01-01 to 2026-03-31 | **Reviews analysed:** 10\n\n"
        "## Top Themes\n1. **Account access & login** — 10 reviews, avg 2.5 stars\n\n"
        '## Real User Quotes\n- "Cannot log in for several days."\n\n'
        "## Action Ideas\n1. Fix session expiry on iOS devices."
    )

    mocker.patch("pulse.analysis.classify.call_llm", return_value=classify_response)
    mocker.patch("pulse.analysis.quote_select.call_llm", return_value=quote_response)
    mocker.patch("pulse.analysis.action_gen.call_llm", return_value=action_response)
    mocker.patch("pulse.render.pulse_note.call_llm_text", return_value=polished_note)

    csv_path = str(FIXTURES / "sample_reviews_minimal.csv")

    run1_out = str(tmp_path / "run1")
    run2_out = str(tmp_path / "run2")
    clean1 = str(tmp_path / "clean1")
    clean2 = str(tmp_path / "clean2")

    Path(run1_out).mkdir()
    Path(run2_out).mkdir()

    r1 = run_pipeline(CONFIG, csv_path, output_dir=run1_out, clean_csv_dir=clean1)
    r2 = run_pipeline(CONFIG, csv_path, output_dir=run2_out, clean_csv_dir=clean2)

    note1 = (Path(run1_out) / "weekly_note.md").read_text()
    note2 = (Path(run2_out) / "weekly_note.md").read_text()

    assert note1 == note2, "Identical inputs must produce identical notes"
    assert r1["input_hash"] == r2["input_hash"], "input_hash must match for same inputs"


# ---------------------------------------------------------------------------
# EC-43: Two independent dry-runs → independent run IDs; no cross-run state
# ---------------------------------------------------------------------------

def test_ec43_independent_dry_runs(tmp_path, monkeypatch):
    """Two dry-runs must produce different run_ids and each write its own run_summary."""
    _setup_tmp_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    csv_path = str(FIXTURES / "sample_reviews.csv")

    out1 = str(tmp_path / "out1")
    out2 = str(tmp_path / "out2")
    clean1 = str(tmp_path / "clean1")
    clean2 = str(tmp_path / "clean2")
    Path(out1).mkdir()
    Path(out2).mkdir()

    r1 = run_pipeline(CONFIG, csv_path, dry_run=True, output_dir=out1, clean_csv_dir=clean1)
    r2 = run_pipeline(CONFIG, csv_path, dry_run=True, output_dir=out2, clean_csv_dir=clean2)

    # Different run IDs
    assert r1["run_id"] != r2["run_id"]
    # Each run produces its own summary
    assert (Path(out1) / "run_summary.json").exists()
    assert (Path(out2) / "run_summary.json").exists()
    # No cross-contamination: each clean CSV dir is independent
    assert (Path(clean1) / "reviews_clean.csv").exists()
    assert (Path(clean2) / "reviews_clean.csv").exists()


# ---------------------------------------------------------------------------
# EC-44: Failure at action generation → prior weekly_note.md unchanged
# ---------------------------------------------------------------------------

def test_ec44_failure_preserves_existing_note(tmp_path, monkeypatch, mocker):
    """
    If the pipeline fails after all LLM steps (at action_gen), the existing
    weekly_note.md must not be touched (EC-44 atomic-write guarantee).
    """
    _setup_tmp_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    output_dir = tmp_path / "outputs"
    output_dir.mkdir(exist_ok=True)

    # Create an existing note that must survive the failed run
    existing_note = "This is the original weekly note — must not be overwritten."
    (output_dir / "weekly_note.md").write_text(existing_note, encoding="utf-8")

    # Mock LLM steps to succeed up to action_gen, then fail
    reviews_data = [
        {
            "review_id": i,
            "platform": "App Store",
            "rating": 2,
            "title_redacted": None,
            "text_redacted": f"Review text {i}.",
            "date": datetime(2026, 5, 15),
            "app_version": None,
            "country": "CA",
            "helpful_votes": None,
            "pii_found": False,
            "theme": "Account access & login",
            "confidence": 0.9,
        }
        for i in range(5)
    ]

    ingest_meta = {"reviews_ingested": 5, "reviews_after_dedup": 5, "rows_dropped_validation": 0, "low_data_warning": False}
    mocker.patch("pulse.orchestrator.load_reviews", return_value=(reviews_data, ingest_meta))
    mocker.patch("pulse.orchestrator.redact_reviews", return_value=reviews_data)
    mocker.patch("pulse.orchestrator.write_clean_csv")
    mocker.patch("pulse.orchestrator.classify_reviews", return_value=reviews_data)
    mocker.patch("pulse.orchestrator.rank_themes", return_value=[
        {"theme": "Account access & login", "review_count": 5, "avg_rating": 2.0, "rank": 1}
    ])
    mocker.patch("pulse.orchestrator.select_top_themes", return_value=["Account access & login"])
    mocker.patch("pulse.orchestrator.select_quotes", return_value=[
        {"theme": "Account access & login", "quote": "Review text 0.", "review_id": 0, "verified": True}
    ])
    mocker.patch(
        "pulse.orchestrator.generate_actions",
        side_effect=RuntimeError("action generation failed"),
    )

    csv_path = str(FIXTURES / "sample_reviews.csv")

    with pytest.raises(RuntimeError, match="action generation failed"):
        run_pipeline(
            CONFIG, csv_path,
            output_dir=str(output_dir),
            clean_csv_dir=str(tmp_path / "clean"),
        )

    # Original weekly_note.md must be completely unchanged (EC-44)
    surviving_note = (output_dir / "weekly_note.md").read_text(encoding="utf-8")
    assert surviving_note == existing_note, (
        "weekly_note.md was overwritten despite pipeline failure — EC-44 violated"
    )
