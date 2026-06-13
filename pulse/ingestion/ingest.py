from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from pulse.ingestion.validators import (
    MissingColumnError,
    normalise_platform,
    parse_date,
    validate_rating,
    validate_required_columns,
    validate_text,
)
from pulse.utils.logging import log

RECOMMENDED_WINDOW_MIN = 8
RECOMMENDED_WINDOW_MAX = 520  # ~10 years; public scrapers may return older data


def load_reviews(csv_path: str, config: Any, run_id: str = "dry-run") -> tuple[list[dict], dict]:
    """
    Load, validate, filter, and deduplicate reviews from csv_path.

    Returns (validated_reviews, metadata) where metadata includes low_data_warning.
    """
    path = Path(csv_path)

    # Read CSV with UTF-8 fallback to Latin-1 (EC-07)
    try:
        df = pd.read_csv(path, encoding="utf-8", dtype=str)
    except UnicodeDecodeError:
        log(run_id, "ingest", "encoding_fallback", path=str(path), encoding="latin-1")
        df = pd.read_csv(path, encoding="latin-1", dtype=str)

    # Normalise column names to lowercase for comparison
    df.columns = [c.strip().lower() for c in df.columns]

    # EC-01 Empty CSV
    if len(df) == 0:
        log(run_id, "ingest", "empty_csv", message="Input CSV is empty — no reviews to process")
        sys.exit(1)

    # EC-03 Missing required columns
    try:
        validate_required_columns(df)
    except MissingColumnError as exc:
        log(run_id, "ingest", "missing_columns", missing=exc.missing)
        sys.exit(1)

    # EC-45 Out-of-range review_window_weeks
    window_weeks = getattr(config, "review_window_weeks", 10)
    if not (RECOMMENDED_WINDOW_MIN <= window_weeks <= RECOMMENDED_WINDOW_MAX):
        log(
            run_id,
            "ingest",
            "window_out_of_range",
            review_window_weeks=window_weeks,
            message=f"review_window_weeks is outside the recommended {RECOMMENDED_WINDOW_MIN}–{RECOMMENDED_WINDOW_MAX} range",
        )

    cutoff = datetime.now() - timedelta(weeks=window_weeks)

    validated: list[dict] = []
    dropped_indices: list[int] = []

    for idx, row in df.iterrows():
        platform = normalise_platform(row.get("platform"))
        if platform is None:
            dropped_indices.append(idx)
            log(run_id, "ingest", "row_dropped", row_index=idx, reason="invalid_platform")
            continue

        rating = validate_rating(row.get("rating"))
        if rating is None:
            dropped_indices.append(idx)
            log(run_id, "ingest", "row_dropped", row_index=idx, reason="invalid_rating")
            continue

        text = validate_text(row.get("text"))
        if text is None:
            dropped_indices.append(idx)
            log(run_id, "ingest", "row_dropped", row_index=idx, reason="blank_or_short_text")
            continue

        date = parse_date(row.get("date"))
        if date is None:
            dropped_indices.append(idx)
            log(run_id, "ingest", "row_dropped", row_index=idx, reason="unparseable_date")
            continue

        # Date window filter
        if date < cutoff:
            continue

        title_val = row.get("title")
        title = str(title_val).strip() if pd.notna(title_val) and str(title_val).strip() else None

        app_version_val = row.get("app_version")
        app_version: Optional[str] = str(app_version_val).strip() if pd.notna(app_version_val) and str(app_version_val).strip() else None

        country_val = row.get("country")
        country: Optional[str] = str(country_val).strip() if pd.notna(country_val) and str(country_val).strip() else None

        helpful_votes: Optional[int] = None
        hv = row.get("helpful_votes")
        if pd.notna(hv) if hv is not None else False:
            try:
                helpful_votes = int(float(hv))
            except (ValueError, TypeError):
                helpful_votes = None

        validated.append({
            "review_id": None,  # assigned after dedup
            "platform": platform,
            "rating": rating,
            "title": title,
            "text": text,
            "date": date,
            "app_version": app_version,
            "country": country,
            "helpful_votes": helpful_votes,
            "_dedup_key": f"{platform}|{date.date().isoformat()}|{text}",
        })

    if dropped_indices:
        log(run_id, "ingest", "rows_dropped_summary", count=len(dropped_indices), indices=dropped_indices)

    # EC-06 Deduplication
    seen: set[str] = set()
    deduped: list[dict] = []
    dup_count = 0
    for record in validated:
        key = record["_dedup_key"]
        if key in seen:
            dup_count += 1
        else:
            seen.add(key)
            deduped.append(record)

    if dup_count:
        log(run_id, "ingest", "duplicates_removed", count=dup_count)

    # Assign sequential review_id
    for i, record in enumerate(deduped):
        record["review_id"] = i
        del record["_dedup_key"]

    low_data_warning = len(deduped) < getattr(config, "min_reviews", 5)
    if low_data_warning:
        log(
            run_id,
            "ingest",
            "low_data_warning",
            review_count=len(deduped),
            min_reviews=getattr(config, "min_reviews", 5),
        )

    log(run_id, "ingest", "ingest_complete", reviews_loaded=len(deduped), dropped=len(dropped_indices), duplicates_removed=dup_count)

    metadata = {
        "low_data_warning": low_data_warning,
        "reviews_ingested": len(deduped) + dup_count,
        "reviews_after_dedup": len(deduped),
        "rows_dropped_validation": len(dropped_indices),
    }

    return deduped, metadata
