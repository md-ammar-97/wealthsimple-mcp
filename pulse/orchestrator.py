"""
Pipeline orchestrator — sequences all 9 steps, mints run IDs, and enforces
EC-44: weekly_note.md and email_draft.txt are only written after complete success.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pulse.analysis.action_gen import generate_actions
from pulse.analysis.classify import classify_reviews, rank_themes, select_top_themes
from pulse.analysis.cluster import classify_with_clustering
from pulse.analysis.embed import embed_reviews
from pulse.analysis.quote_select import select_quotes
from pulse.delivery.docs_mcp import append_doc_section
from pulse.delivery.gmail_mcp import create_gmail_draft
from pulse.delivery.local import write_artifact
from pulse.ingestion.ingest import load_reviews
from pulse.ledger.run_ledger import (
    append_ledger,
    build_delivery_key,
    build_period_key,
    check_delivery_guard,
    compute_input_hash,
    mint_run_id,
    write_run_summary,
)
from pulse.privacy.redact import redact_reviews, write_clean_csv
from pulse.render.email_draft import render_email_draft
from pulse.render.pulse_note import MissingUpstreamFieldError, generate_pulse_note
from pulse.utils.logging import log


def run_pipeline(
    config: Any,
    input_csv: str,
    dry_run: bool = False,
    force: bool = False,
    output_dir: str = "outputs",
    run_id: str | None = None,
    clean_csv_dir: str = "data/output",
) -> dict:
    """
    Execute the full review-pulse pipeline.

    Parameters
    ----------
    config       : Namespace from pulse.config.load_config()
    input_csv    : Path to the input reviews CSV
    dry_run      : If True, stop after redaction (no LLM calls, no note/email)
    force        : If True, skip the delivery-guard idempotency check
    output_dir   : Directory for weekly_note.md, email_draft.txt, run_summary.json
    run_id       : Override the minted run ID (useful for tests / reruns)
    clean_csv_dir: Directory for reviews_clean.csv (separate from output_dir)
    """
    # ── IDs ──────────────────────────────────────────────────────────────────
    if run_id is None:
        run_id = mint_run_id()

    config_path = "config/pipeline.yaml"
    try:
        input_hash = compute_input_hash(input_csv, config_path)
    except FileNotFoundError:
        input_hash = "sha256:unknown"

    run_date = datetime.now(timezone.utc)
    period_key = build_period_key(run_date)
    delivery_key = build_delivery_key(period_key)
    started_at = run_date.isoformat()

    run_data: dict = {
        "run_id": run_id,
        "input_hash": input_hash,
        "period_key": period_key,
        "delivery_key": delivery_key,
        "product": getattr(config, "product", "Wealthsimple Canada"),
        "input_csv": input_csv,
        "review_window_weeks": getattr(config, "review_window_weeks", 10),
        "model": getattr(config, "model", ""),
        "started_at": started_at,
        "delivery": {"mode": getattr(config, "delivery_mode", "local")},
        "errors": [],
    }

    output_paths = {
        "clean_csv": str(Path(clean_csv_dir) / "reviews_clean.csv"),
        "weekly_note": str(Path(output_dir) / "weekly_note.md"),
        "email_draft": str(Path(output_dir) / "email_draft.txt"),
        "run_summary": str(Path(output_dir) / "run_summary.json"),
    }

    log(
        run_id, "pipeline", "run_start",
        dry_run=dry_run, input_csv=input_csv, period_key=period_key,
    )

    # ── Delivery guard ────────────────────────────────────────────────────────
    if not force and check_delivery_guard(period_key, delivery_key):
        log(run_id, "pipeline", "delivery_already_done",
            period_key=period_key, delivery_key=delivery_key)

    # ── Steps ─────────────────────────────────────────────────────────────────
    try:
        # Step 1 — Ingest
        log(run_id, "pipeline", "step_start", step=1, name="ingest")
        reviews, ingest_meta = load_reviews(input_csv, config, run_id=run_id)
        log(run_id, "pipeline", "step_done", step=1,
            reviews_ingested=ingest_meta.get("reviews_ingested", len(reviews)))

        run_data.update({
            "reviews_ingested": ingest_meta.get("reviews_ingested", len(reviews)),
            "reviews_after_dedup": ingest_meta.get("reviews_after_dedup", len(reviews)),
            "rows_dropped_validation": ingest_meta.get("rows_dropped_validation", 0),
            "low_data_warning": ingest_meta.get("low_data_warning", False),
        })

        # Step 2 — Redact + write clean CSV
        log(run_id, "pipeline", "step_start", step=2, name="redact")
        redacted = redact_reviews(reviews, run_id=run_id)
        write_clean_csv(redacted, output_paths["clean_csv"], run_id=run_id)

        rows_with_pii = sum(1 for r in redacted if r.get("pii_found"))
        rows_excluded = len(reviews) - len(redacted)
        run_data.update({
            "rows_with_pii": rows_with_pii,
            "rows_excluded_post_redaction": rows_excluded,
        })
        log(run_id, "pipeline", "step_done", step=2,
            redacted=len(redacted), excluded=rows_excluded)

        # ── Dry-run exit ──────────────────────────────────────────────────────
        if dry_run:
            run_data.update({
                "status": "dry_run",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "output_paths": {"clean_csv": output_paths["clean_csv"]},
            })
            write_run_summary(run_data, config, output_paths["run_summary"])
            log(run_id, "pipeline", "run_complete", status="dry_run")
            return run_data

        # Step 3 — Classify (embedding + clustering when enabled, else LLM batches)
        log(run_id, "pipeline", "step_start", step=3, name="classify")
        use_clustering = getattr(config, "use_clustering", True)
        if use_clustering:
            log(run_id, "pipeline", "embed_start", model=getattr(config, "embed_model", "BAAI/bge-small-en-v1.5"))
            embeddings = embed_reviews(redacted, run_id=run_id)
            log(run_id, "pipeline", "embed_done", shape=list(embeddings.shape))
            themed = classify_with_clustering(redacted, embeddings, config, run_id=run_id)
        else:
            themed = classify_reviews(redacted, config, run_id=run_id)
        log(run_id, "pipeline", "step_done", step=3, themed=len(themed))

        # Step 4 — Rank themes
        log(run_id, "pipeline", "step_start", step=4, name="rank_themes")
        ranked = rank_themes(themed, config, run_id=run_id)
        n_note = getattr(config, "note_themes", 3)
        top_themes = select_top_themes(ranked, n=n_note)
        log(run_id, "pipeline", "step_done", step=4,
            themes_found=len(ranked), top_themes=top_themes)

        run_data.update({
            "themes_found": len(ranked),
            "themes_in_note": len(top_themes),
            "selected_themes": top_themes,
        })

        # Step 5 — Select quotes
        log(run_id, "pipeline", "step_start", step=5, name="quote_select")
        quotes = select_quotes(themed, top_themes, config, run_id=run_id)
        log(run_id, "pipeline", "step_done", step=5, quotes=len(quotes))

        # Step 6 — Generate actions
        log(run_id, "pipeline", "step_start", step=6, name="action_gen")
        actions = generate_actions(top_themes, quotes, config, run_id=run_id)
        log(run_id, "pipeline", "step_done", step=6, actions=len(actions))

        # Step 7 — Generate pulse note (in memory — NOT written yet; EC-44)
        log(run_id, "pipeline", "step_start", step=7, name="pulse_note")
        note_result = generate_pulse_note(
            ranked, quotes, actions, redacted, config, run_id=run_id,
            low_data_warning=ingest_meta.get("low_data_warning", False),
        )
        log(run_id, "pipeline", "step_done", step=7,
            word_count=note_result["word_count"],
            note_truncated=note_result["note_truncated"])

        # Step 8 — Render email draft (in memory — NOT written yet; EC-44)
        log(run_id, "pipeline", "step_start", step=8, name="email_draft")
        email_text = render_email_draft(note_result["note_text"], config, run_id=run_id)
        log(run_id, "pipeline", "step_done", step=8)

        # ── All steps succeeded → write output artifacts atomically (EC-44) ──
        write_artifact(note_result["note_text"], output_paths["weekly_note"], run_id=run_id)
        write_artifact(email_text, output_paths["email_draft"], run_id=run_id)

        # Step 9 — Ledger (initial write before delivery)
        run_data.update({
            "status": "success",
            "note_word_count": note_result["word_count"],
            "note_truncated": note_result["note_truncated"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output_paths": output_paths,
        })

        # Step 10 — Optional MCP delivery via google-mcp-server
        # Delivery failures are non-fatal: logged and added to errors, pipeline stays "success"
        try:
            append_doc_section(
                note_result["note_text"], run_data, config,
                run_id=run_id, force=force,
            )
        except Exception as delivery_exc:
            log(run_id, "delivery", "docs_mcp_error", error=str(delivery_exc))
            run_data["errors"].append(f"docs_delivery: {delivery_exc}")

        try:
            create_gmail_draft(
                email_text, run_data, config,
                run_id=run_id, force=force,
            )
        except Exception as delivery_exc:
            log(run_id, "delivery", "gmail_mcp_error", error=str(delivery_exc))
            run_data["errors"].append(f"gmail_delivery: {delivery_exc}")

        # Surface delivery errors in CI logs (errors array is written to artifact only)
        if run_data.get("errors"):
            import sys
            for _err in run_data["errors"]:
                print(f"[DELIVERY ERROR] {_err}", file=sys.stderr)

        # Write final summary (includes delivery results) and ledger
        write_run_summary(run_data, config, output_paths["run_summary"])
        append_ledger(run_data, config)

        duration = (
            datetime.fromisoformat(run_data["completed_at"])
            - datetime.fromisoformat(started_at)
        ).total_seconds()
        log(run_id, "pipeline", "run_complete", status="success", duration_seconds=duration)

    except Exception as exc:
        run_data.update({
            "status": "error",
            "errors": [str(exc)],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        log(run_id, "pipeline", "run_error", error=str(exc))
        try:
            write_run_summary(run_data, config, output_paths["run_summary"])
        except Exception:
            pass
        raise

    return run_data
