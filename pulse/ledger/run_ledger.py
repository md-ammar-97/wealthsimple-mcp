from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def mint_run_id() -> str:
    """Produce a sortable, human-readable run identifier."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = str(uuid.uuid4()).replace("-", "")[:6]
    return f"run-{timestamp}-{suffix}"


def compute_input_hash(csv_path: str, config_path: str) -> str:
    """Deterministic hash of (csv_bytes + config_bytes). Detects re-runs on same input."""
    csv_bytes = Path(csv_path).read_bytes()
    config_bytes = Path(config_path).read_bytes()
    digest = hashlib.sha256(csv_bytes + config_bytes).hexdigest()[:12]
    return f"sha256:{digest}"


def build_period_key(run_date: datetime) -> str:
    """ISO-week period key, e.g. 'wealthsimple-2026-W23'."""
    iso_year, week, _ = run_date.isocalendar()
    return f"wealthsimple-{iso_year}-W{week:02d}"


def build_delivery_key(period_key: str) -> str:
    """Delivery idempotency key for email delivery."""
    return f"{period_key}-email"


def write_run_summary(
    run_data: dict,
    config: Any,
    output_path: str = "outputs/run_summary.json",
) -> None:
    """Write run_summary.json to output_path; also archive a per-run copy."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(run_data, indent=2, default=str)
    path.write_text(serialised, encoding="utf-8")

    # Per-run archive so pulse status can look up any historical run.
    run_id = run_data.get("run_id", "unknown")
    per_run = Path("data/runs") / f"{run_id}.json"
    per_run.parent.mkdir(parents=True, exist_ok=True)
    per_run.write_text(serialised, encoding="utf-8")


def append_ledger(run_data: dict, config: Any) -> None:
    """Append a summary entry (no review text / PII) to data/runs/ledger.json."""
    ledger_path = Path("data/runs/ledger.json")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    if ledger_path.exists():
        try:
            raw = json.loads(ledger_path.read_text(encoding="utf-8"))
            entries = raw if isinstance(raw, list) else [raw]
        except (json.JSONDecodeError, Exception):
            entries = []

    entry = {
        "run_id": run_data.get("run_id"),
        "input_hash": run_data.get("input_hash"),
        "period_key": run_data.get("period_key"),
        "delivery_key": run_data.get("delivery_key"),
        "status": run_data.get("status"),
        "started_at": run_data.get("started_at"),
        "completed_at": run_data.get("completed_at"),
        "reviews_ingested": run_data.get("reviews_ingested"),
        "themes_in_note": run_data.get("themes_in_note"),
        "note_word_count": run_data.get("note_word_count"),
        "delivery": run_data.get("delivery"),
    }
    entries.append(entry)
    ledger_path.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")


def read_run_summary(run_id: str) -> dict:
    """
    Retrieve the run summary for *run_id*.
    Checks: per-run archive → latest outputs/run_summary.json → ledger entries.
    """
    per_run = Path("data/runs") / f"{run_id}.json"
    if per_run.exists():
        return json.loads(per_run.read_text(encoding="utf-8"))

    summary_path = Path("outputs/run_summary.json")
    if summary_path.exists():
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        if data.get("run_id") == run_id:
            return data

    ledger_path = Path("data/runs/ledger.json")
    if ledger_path.exists():
        try:
            for entry in json.loads(ledger_path.read_text(encoding="utf-8")):
                if entry.get("run_id") == run_id:
                    return entry
        except (json.JSONDecodeError, Exception):
            pass

    raise FileNotFoundError(f"Run summary not found for run_id: {run_id}")


def check_delivery_guard(period_key: str, delivery_key: str) -> bool:
    """Return True if a successful delivery for this period is already recorded."""
    ledger_path = Path("data/runs/ledger.json")
    if not ledger_path.exists():
        return False
    try:
        for entry in json.loads(ledger_path.read_text(encoding="utf-8")):
            if (
                entry.get("period_key") == period_key
                and entry.get("delivery_key") == delivery_key
                and entry.get("status") == "success"
            ):
                return True
    except (json.JSONDecodeError, Exception):
        pass
    return False
