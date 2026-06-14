"""
Unit tests for pulse/ledger/run_ledger.py — key minting + write/read.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.ledger.run_ledger import (
    append_ledger,
    build_delivery_key,
    build_period_key,
    check_delivery_guard,
    compute_input_hash,
    mint_run_id,
    read_run_summary,
    write_run_summary,
)

CONFIG = SimpleNamespace(ledger_backend="json")

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# mint_run_id
# ---------------------------------------------------------------------------

def test_mint_run_id_format():
    run_id = mint_run_id()
    assert run_id.startswith("run-")
    # Format: run-YYYYMMDDTHHMMSSz-xxxxxx
    assert re.match(r"^run-\d{8}T\d{6}Z-[0-9a-f]{6}$", run_id), f"bad format: {run_id}"


def test_mint_run_id_unique():
    ids = {mint_run_id() for _ in range(20)}
    assert len(ids) == 20


# ---------------------------------------------------------------------------
# compute_input_hash
# ---------------------------------------------------------------------------

def test_compute_input_hash_format():
    csv_path = str(FIXTURES / "sample_reviews.csv")
    h = compute_input_hash(csv_path, "config/pipeline.yaml")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 12


def test_compute_input_hash_deterministic():
    csv_path = str(FIXTURES / "sample_reviews.csv")
    h1 = compute_input_hash(csv_path, "config/pipeline.yaml")
    h2 = compute_input_hash(csv_path, "config/pipeline.yaml")
    assert h1 == h2


def test_compute_input_hash_differs_for_different_csv():
    h1 = compute_input_hash(
        str(FIXTURES / "sample_reviews.csv"), "config/pipeline.yaml"
    )
    h2 = compute_input_hash(
        str(FIXTURES / "sample_reviews_minimal.csv"), "config/pipeline.yaml"
    )
    assert h1 != h2


# ---------------------------------------------------------------------------
# build_period_key / build_delivery_key
# ---------------------------------------------------------------------------

def test_build_period_key_format():
    dt = datetime(2026, 6, 8, tzinfo=timezone.utc)
    key = build_period_key(dt)
    assert re.match(r"^wealthsimple-\d{4}-W\d{2}$", key)


def test_build_period_key_iso_week():
    # 2026-06-08 is ISO week 24
    dt = datetime(2026, 6, 8, tzinfo=timezone.utc)
    key = build_period_key(dt)
    assert key == "wealthsimple-2026-W24"


def test_build_delivery_key():
    key = build_delivery_key("wealthsimple-2026-W24")
    assert key == "wealthsimple-2026-W24-email"


def test_build_delivery_key_includes_email_mode():
    key = build_delivery_key("wealthsimple-2026-W24", "send")
    assert key == "wealthsimple-2026-W24-email-send"


# ---------------------------------------------------------------------------
# write_run_summary / read_run_summary
# ---------------------------------------------------------------------------

def test_write_and_read_run_summary(tmp_path, monkeypatch):
    """write_run_summary persists to disk; read_run_summary retrieves it."""
    # Redirect data/runs and outputs to tmp_path
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "runs").mkdir(parents=True)
    (tmp_path / "outputs").mkdir()

    run_id = mint_run_id()
    run_data = {
        "run_id": run_id,
        "input_hash": "sha256:abc123def456",
        "period_key": "wealthsimple-2026-W24",
        "delivery_key": "wealthsimple-2026-W24-email",
        "status": "success",
        "started_at": "2026-06-08T10:00:00+00:00",
        "completed_at": "2026-06-08T10:05:00+00:00",
        "reviews_ingested": 49,
    }

    out_path = str(tmp_path / "outputs" / "run_summary.json")
    write_run_summary(run_data, CONFIG, output_path=out_path)

    # Per-run archive should also exist
    per_run = tmp_path / "data" / "runs" / f"{run_id}.json"
    assert per_run.exists()

    retrieved = read_run_summary(run_id)
    assert retrieved["run_id"] == run_id
    assert retrieved["status"] == "success"


def test_read_run_summary_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        read_run_summary("run-nonexistent")


# ---------------------------------------------------------------------------
# append_ledger / check_delivery_guard
# ---------------------------------------------------------------------------

def test_append_and_read_ledger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "runs").mkdir(parents=True)

    run_data = {
        "run_id": "run-20260608T100000Z-abc123",
        "input_hash": "sha256:abc123def456",
        "period_key": "wealthsimple-2026-W24",
        "delivery_key": "wealthsimple-2026-W24-email",
        "status": "success",
        "started_at": "2026-06-08T10:00:00",
        "completed_at": "2026-06-08T10:05:00",
        "reviews_ingested": 49,
        "themes_in_note": 3,
        "note_word_count": 210,
        "delivery": {"mode": "local"},
    }

    append_ledger(run_data, CONFIG)

    ledger_path = tmp_path / "data" / "runs" / "ledger.json"
    assert ledger_path.exists()
    entries = json.loads(ledger_path.read_text())
    assert len(entries) == 1
    assert entries[0]["run_id"] == run_data["run_id"]
    assert entries[0]["status"] == "success"


def test_append_ledger_accumulates_entries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "runs").mkdir(parents=True)

    for i in range(3):
        run_data = {
            "run_id": f"run-{i}",
            "period_key": f"wealthsimple-2026-W{i + 1:02d}",
            "delivery_key": f"wealthsimple-2026-W{i + 1:02d}-email",
            "status": "success",
        }
        append_ledger(run_data, CONFIG)

    entries = json.loads(
        (tmp_path / "data" / "runs" / "ledger.json").read_text()
    )
    assert len(entries) == 3


def test_check_delivery_guard_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "runs").mkdir(parents=True)

    run_data = {
        "run_id": "run-test",
        "period_key": "wealthsimple-2026-W24",
        "delivery_key": "wealthsimple-2026-W24-email",
        "status": "success",
    }
    append_ledger(run_data, CONFIG)

    assert check_delivery_guard(
        "wealthsimple-2026-W24", "wealthsimple-2026-W24-email"
    ) is True


def test_check_delivery_guard_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert check_delivery_guard("wealthsimple-2026-W99", "wealthsimple-2026-W99-email") is False


def test_check_delivery_guard_different_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "runs").mkdir(parents=True)

    run_data = {
        "run_id": "run-fail",
        "period_key": "wealthsimple-2026-W24",
        "delivery_key": "wealthsimple-2026-W24-email",
        "status": "error",
    }
    append_ledger(run_data, CONFIG)

    # Error status should NOT trigger the guard
    assert check_delivery_guard(
        "wealthsimple-2026-W24", "wealthsimple-2026-W24-email"
    ) is False
