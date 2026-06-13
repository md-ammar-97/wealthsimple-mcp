from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from pulse.privacy.patterns import PATTERNS
from pulse.utils.logging import log


def _apply_patterns(text: str) -> tuple[str, bool]:
    """Apply all PII patterns to text. Returns (redacted_text, pii_found)."""
    result = text
    pii_found = False
    for pattern, replacement in PATTERNS:
        new = pattern.sub(replacement, result)
        if new != result:
            pii_found = True
        result = new
    return result, pii_found


def _post_scan(text: str) -> bool:
    """Re-scan redacted text; return True if any PII pattern still matches."""
    for pattern, _ in PATTERNS:
        if pattern.search(text):
            return True
    return False


def redact_reviews(validated_reviews: list[dict], run_id: str = "dry-run") -> list[dict]:
    """
    Apply PII redaction to title and text fields.
    Excludes rows where text_redacted < 5 chars after redaction (EC-11).
    """
    redacted: list[dict] = []
    pii_count = 0
    excluded_count = 0

    for record in validated_reviews:
        title_raw: Optional[str] = record.get("title")
        text_raw: str = record["text"]

        title_redacted: Optional[str] = None
        title_pii = False
        if title_raw:
            title_redacted, title_pii = _apply_patterns(title_raw)

        text_redacted, text_pii = _apply_patterns(text_raw)

        pii_found = title_pii or text_pii

        # Post-scan for any remaining PII
        if not pii_found:
            pii_found = _post_scan(text_redacted) or (
                title_redacted is not None and _post_scan(title_redacted)
            )
        else:
            # Post-scan to catch anything missed
            still_has_pii = _post_scan(text_redacted)
            if still_has_pii:
                pii_found = True

        if pii_found:
            pii_count += 1

        # EC-11: exclude rows where text is fully redacted
        if len(text_redacted.strip()) < 5:
            excluded_count += 1
            log(
                run_id,
                "redact",
                "row_excluded_post_redaction",
                review_id=record.get("review_id"),
                reason="text_fully_redacted",
            )
            continue

        redacted_record = {**record, "title_redacted": title_redacted, "text_redacted": text_redacted, "pii_found": pii_found}
        redacted.append(redacted_record)

    log(
        run_id,
        "redact",
        "redaction_complete",
        total=len(validated_reviews),
        pii_flagged=pii_count,
        excluded=excluded_count,
        output_count=len(redacted),
    )

    return redacted


def write_clean_csv(redacted_reviews: list[dict], output_path: str, run_id: str = "dry-run") -> None:
    """
    Write reviews_clean.csv. Never writes raw title or text columns.
    Columns: review_id, platform, rating, title_redacted, text_redacted,
             date, app_version, country, helpful_votes, pii_found
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "review_id",
        "platform",
        "rating",
        "title_redacted",
        "text_redacted",
        "date",
        "app_version",
        "country",
        "helpful_votes",
        "pii_found",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in redacted_reviews:
            row = {
                "review_id": record.get("review_id", ""),
                "platform": record.get("platform", ""),
                "rating": record.get("rating", ""),
                "title_redacted": record.get("title_redacted") or "",
                "text_redacted": record.get("text_redacted", ""),
                "date": record["date"].strftime("%Y-%m-%d") if record.get("date") else "",
                "app_version": record.get("app_version") or "",
                "country": record.get("country") or "",
                "helpful_votes": record.get("helpful_votes") if record.get("helpful_votes") is not None else "",
                "pii_found": record.get("pii_found", False),
            }
            writer.writerow(row)

    log(run_id, "redact", "clean_csv_written", path=str(path), row_count=len(redacted_reviews))
