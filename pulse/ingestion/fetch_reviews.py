"""
Fetch public Wealthsimple Canada app reviews.

Sources:
  - Google Play Store via google-play-scraper (public, no auth)

Columns kept per the problem statement (PII columns dropped at source):
  platform, rating, title, text, date, app_version, country, helpful_votes

Columns intentionally NOT written:
  reviewId, userName, userImage, reviewCreatedVersion, at, replyContent, repliedAt
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

RAW_FIELDNAMES = ["platform", "rating", "title", "text", "date", "app_version", "country", "helpful_votes"]


def fetch_playstore_reviews(package_id: str, max_reviews: int = 500) -> list[dict]:
    """
    Pull reviews from Google Play via google-play-scraper.
    Fetches up to max_reviews entries (newest-first).
    No date filtering — all available reviews are returned.
    """
    from google_play_scraper import Sort, reviews as gp_reviews  # type: ignore

    all_reviews: list[dict] = []
    continuation_token = None

    while len(all_reviews) < max_reviews:
        try:
            result, continuation_token = gp_reviews(
                package_id,
                lang="en",
                country="ca",
                sort=Sort.NEWEST,
                count=min(200, max_reviews - len(all_reviews)),
                continuation_token=continuation_token,
            )
        except Exception as exc:
            print(f"  [Google Play] fetch error: {exc}")
            break

        if not result:
            break

        for r in result:
            at: datetime | None = r.get("at")
            all_reviews.append({
                "platform": "Google Play",
                "rating": r.get("score", ""),
                "title": "",
                "text": r.get("content", "") or "",
                "date": at.strftime("%Y-%m-%d") if at else "",
                "app_version": r.get("appVersion", "") or "",
                "country": "CA",
                "helpful_votes": r.get("thumbsUpCount", "") or "",
            })

        if not continuation_token:
            break

        time.sleep(0.4)

    print(f"  [Google Play] fetched {len(all_reviews)} reviews")
    return all_reviews


def save_raw_reviews(reviews: list[dict], output_path: str) -> int:
    """Write reviews to CSV. Returns number of rows written."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(reviews)

    return len(reviews)


def fetch_all(package_id: str, output_path: str, weeks: int = 10) -> int:
    """Fetch from Google Play and save reviews_raw.csv."""
    print(f"Fetching reviews (target window: last {weeks} weeks, ending {datetime.now().strftime('%Y-%m-%d')}) ...")

    reviews = fetch_playstore_reviews(package_id, max_reviews=500)

    count = save_raw_reviews(reviews, output_path)
    print(f"  saved {count} total reviews to {output_path}")
    return count


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    from pulse.config import load_config

    cfg = load_config(
        str(project_root / "config" / "pipeline.yaml"),
        str(project_root / "config" / "delivery.yaml"),
    )
    fetch_all(
        package_id=cfg.playstore_package_id,
        output_path=str(project_root / "data" / "input" / "reviews_raw.csv"),
        weeks=cfg.review_window_weeks,
    )
