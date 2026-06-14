"""
CLI entry points:
  pulse run      --input PATH [--run-id ID] [--force] [--output-dir DIR]
  pulse dry-run  --input PATH [--output-dir DIR]
  pulse status   --run-id ID
"""
from __future__ import annotations

import json
import sys

import click

from pulse.config import load_config
from pulse.ingestion.fetch_reviews import fetch_all
from pulse.ingestion.normalize import normalize_reviews
from pulse.ledger.run_ledger import read_run_summary
from pulse.orchestrator import run_pipeline


@click.group()
def main() -> None:
    """Wealthsimple App Review Insights — pulse pipeline CLI."""


@main.command()
@click.option("--input", "input_csv", required=True, help="Path to input reviews CSV")
@click.option("--run-id", default=None, help="Override auto-minted run ID")
@click.option("--force", is_flag=True, default=False,
              help="Skip idempotency guard and re-deliver even if week already processed")
@click.option("--skip-delivery", is_flag=True, default=False,
              help="Generate artifacts without Google Docs or Gmail delivery")
@click.option("--output-dir", default="outputs", show_default=True,
              help="Directory for weekly_note.md, email_draft.txt, run_summary.json")
def run(
    input_csv: str,
    run_id: str | None,
    force: bool,
    skip_delivery: bool,
    output_dir: str,
) -> None:
    """Run the full pipeline (ingest -> classify -> note -> email -> ledger)."""
    config = load_config()
    try:
        result = run_pipeline(
            config, input_csv,
            dry_run=False, force=force,
            output_dir=output_dir, run_id=run_id,
            skip_delivery=skip_delivery,
        )
        click.echo(f"Run complete: {result['run_id']}  status={result['status']}")
    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Pipeline error: {exc}", err=True)
        sys.exit(1)


@main.command(name="dry-run")
@click.option("--input", "input_csv", required=True, help="Path to input reviews CSV")
@click.option("--output-dir", default="outputs", show_default=True,
              help="Directory for run_summary.json")
def dry_run(input_csv: str, output_dir: str) -> None:
    """Ingest + redact only — no LLM calls, no note or email written."""
    config = load_config()
    try:
        result = run_pipeline(config, input_csv, dry_run=True, output_dir=output_dir)
        click.echo(f"Dry-run complete: {result['run_id']}")
    except SystemExit:
        raise
    except Exception as exc:
        click.echo(f"Dry-run error: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.option("--weeks", default=10, show_default=True,
              help="Number of weeks of reviews to fetch (recommended 8–12)")
@click.option("--raw-output", default="data/input/reviews_raw.csv", show_default=True,
              help="Path for raw reviews CSV (all fetched, no filters)")
@click.option("--clean-output", default="data/output/reviews_clean.csv", show_default=True,
              help="Path for normalized/filtered reviews CSV")
def fetch(weeks: int, raw_output: str, clean_output: str) -> None:
    """Fetch real reviews from Google Play, then normalize."""
    config = load_config()
    pkg_id = getattr(config, "playstore_package_id", "com.wealthsimple")

    count = fetch_all(package_id=pkg_id, output_path=raw_output, weeks=weeks)
    if count == 0:
        click.echo("No reviews fetched — check your network connection.", err=True)
        sys.exit(1)

    stats = normalize_reviews(raw_path=raw_output, clean_path=clean_output)
    click.echo(
        f"Fetch complete: {stats['total_raw']} raw -> {stats['kept']} normalized "
        f"(raw: {raw_output}  clean: {clean_output})"
    )


@main.command()
@click.option("--run-id", required=True, help="Run ID returned by pulse run or dry-run")
def status(run_id: str) -> None:
    """Print the stored run summary for the given run ID."""
    try:
        data = read_run_summary(run_id)
        click.echo(json.dumps(data, indent=2, default=str))
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
