"""
Unit tests for pulse/ingestion/ingest.py — covers EC-01 to EC-09 and EC-45.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pulse.ingestion.ingest import load_reviews
from pulse.ingestion.validators import MissingColumnError

FIXTURES = Path(__file__).parent.parent / "fixtures"


def make_config(**overrides):
    defaults = dict(
        review_window_weeks=10,
        min_reviews=5,
        max_review_chars=2000,
        batch_size=50,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def recent_date(days_ago: int = 10) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# EC-01: Empty CSV → SystemExit; no output files written
# ---------------------------------------------------------------------------
def test_ec01_empty_csv(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("platform,rating,title,text,date\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        load_reviews(str(empty_csv), make_config())


# ---------------------------------------------------------------------------
# EC-02: < min_reviews → low_data_warning: True
# ---------------------------------------------------------------------------
def test_ec02_low_data_warning():
    reviews, meta = load_reviews(str(FIXTURES / "sample_reviews_minimal.csv"), make_config())
    assert meta["low_data_warning"] is True


# ---------------------------------------------------------------------------
# EC-03: Missing required column → MissingColumnError / SystemExit
# ---------------------------------------------------------------------------
def test_ec03_missing_column_rating(tmp_path):
    csv_path = tmp_path / "missing_rating.csv"
    csv_path.write_text(
        f"platform,title,text,date\n"
        f"App Store,Good app,The app works well.,{recent_date()}\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        load_reviews(str(csv_path), make_config())


def test_ec03_missing_column_text(tmp_path):
    csv_path = tmp_path / "missing_text.csv"
    csv_path.write_text(
        f"platform,rating,date\n"
        f"App Store,4,{recent_date()}\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        load_reviews(str(csv_path), make_config())


# ---------------------------------------------------------------------------
# EC-04: Single platform (Google Play only) — passes; no fabrication
# ---------------------------------------------------------------------------
def test_ec04_single_platform(tmp_path):
    csv_path = tmp_path / "gplay_only.csv"
    rows = "\n".join(
        [f"Google Play,{r},Title {r},Review text number {r} is valid.,{recent_date(i)}"
         for i, r in enumerate(range(1, 8), start=1)]
    )
    csv_path.write_text(f"platform,rating,title,text,date\n{rows}\n", encoding="utf-8")
    reviews, meta = load_reviews(str(csv_path), make_config())
    platforms = {r["platform"] for r in reviews}
    assert platforms == {"Google Play"}
    assert "App Store" not in platforms


# ---------------------------------------------------------------------------
# EC-05: Mix of date formats — ISO and DD/MM/YYYY parse; others dropped
# ---------------------------------------------------------------------------
def test_ec05_mixed_date_formats(tmp_path):
    csv_path = tmp_path / "mixed_dates.csv"
    csv_path.write_text(
        "platform,rating,title,text,date\n"
        f"App Store,3,Good,This app works great for managing investments.,2026-05-15\n"
        f"App Store,4,Great,I really enjoy using this application daily.,15/05/2026\n"
        f"App Store,5,Useful,The portfolio view is useful and easy to read.,05/15/2026\n"
        f"App Store,5,Fast,The application loads quickly every morning.,2026-05-15T08:30:00Z\n"
        f"App Store,2,Bad,The app crashes constantly and I cannot use it.,March 15 2026\n",
        encoding="utf-8",
    )
    config = make_config(review_window_weeks=52)
    reviews, meta = load_reviews(str(csv_path), config)
    assert len(reviews) == 4
    assert meta["validation_drop_reasons"] == {"unparseable_date": 1}


def test_platform_aliases_are_normalised(tmp_path):
    csv_path = tmp_path / "platform_aliases.csv"
    rows = [
        f"iOS App Store,5,Great,The app makes investing straightforward and clear.,{recent_date(1)}",
        f"Apple App Store,4,Useful,The account overview is useful every morning.,{recent_date(2)}",
        f"Android,3,Fine,The Android application generally works well.,{recent_date(3)}",
        f"Google_Play,2,Slow,The application can be slow during market open.,{recent_date(4)}",
    ]
    csv_path.write_text(
        "platform,rating,title,text,date\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    reviews, meta = load_reviews(str(csv_path), make_config(min_reviews=1))

    assert [review["platform"] for review in reviews] == [
        "App Store",
        "App Store",
        "Google Play",
        "Google Play",
    ]
    assert meta["rows_dropped_validation"] == 0


def test_zero_valid_rows_reports_rejection_reasons(tmp_path):
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text(
        "platform,rating,text,date\n"
        "Unknown Store,5,This review has enough text.,2026-05-15\n"
        "App Store,9,This rating is invalid.,2026-05-15\n"
        "Google Play,4,This date cannot be parsed.,not-a-date\n",
        encoding="utf-8",
    )

    reviews, meta = load_reviews(
        str(csv_path),
        make_config(review_window_weeks=52),
    )

    assert reviews == []
    assert meta["validation_drop_reasons"] == {
        "invalid_platform": 1,
        "invalid_rating": 1,
        "unparseable_date": 1,
    }
    assert "invalid_platform=1" in meta["validation_error"]
    assert "invalid_rating=1" in meta["validation_error"]
    assert "unparseable_date=1" in meta["validation_error"]


# ---------------------------------------------------------------------------
# EC-06: Duplicate rows — only 1 survives; count logged
# ---------------------------------------------------------------------------
def test_ec06_duplicates():
    reviews, meta = load_reviews(
        str(FIXTURES / "sample_reviews.csv"),
        make_config(),
    )
    # The fixture has 3 duplicate rows of "Keeps logging me out"
    # Verify that duplicates were removed (reviews_ingested > reviews_after_dedup would indicate it)
    assert meta["reviews_after_dedup"] < meta["reviews_ingested"] + meta.get("rows_dropped_validation", 0)


def test_ec06_explicit_duplicates(tmp_path):
    """Row repeated 5 times → 1 row survives."""
    csv_path = tmp_path / "dupes.csv"
    header = "platform,rating,title,text,date\n"
    row = f"App Store,3,Title,The exact same review text repeated here.,{recent_date()}\n"
    csv_path.write_text(header + row * 5, encoding="utf-8")
    reviews, meta = load_reviews(str(csv_path), make_config(min_reviews=1))
    assert len(reviews) == 1


# ---------------------------------------------------------------------------
# EC-07: Latin-1 encoded CSV — decoded without crash
# ---------------------------------------------------------------------------
def test_ec07_latin1_encoding(tmp_path):
    csv_path = tmp_path / "latin1.csv"
    content = (
        "platform,rating,title,text,date\n"
        f"App Store,5,Tr\xe8s bien,Tr\xe8s bien l'application bancaire.,{recent_date()}\n"
        f"App Store,4,Bon,L'application fonctionne parfaitement bien.,{recent_date(2)}\n"
        f"App Store,3,Moyen,L'\xe9quipe de support est lente \xe0 r\xe9pondre.,{recent_date(3)}\n"
        f"App Store,2,Mauvais,L'application est lente et plante souvent.,{recent_date(4)}\n"
        f"App Store,1,Terrible,Impossible de se connecter depuis plusieurs jours.,{recent_date(5)}\n"
    )
    csv_path.write_bytes(content.encode("latin-1"))
    reviews, meta = load_reviews(str(csv_path), make_config())
    assert len(reviews) > 0
    texts = [r["text"] for r in reviews]
    assert any("è" in t or "é" in t for t in texts)


# ---------------------------------------------------------------------------
# EC-08: Blank text → row dropped
# ---------------------------------------------------------------------------
def test_ec08_blank_text_dropped(tmp_path):
    csv_path = tmp_path / "blank_text.csv"
    lines = [f"App Store,{i},Title,{'   ' if i <= 3 else 'Valid text about app performance.'},{ recent_date(i)}"
             for i in range(1, 8)]
    csv_path.write_text("platform,rating,title,text,date\n" + "\n".join(lines) + "\n", encoding="utf-8")
    reviews, meta = load_reviews(str(csv_path), make_config())
    assert meta["rows_dropped_validation"] >= 3
    for r in reviews:
        assert r["text"].strip() != ""


# ---------------------------------------------------------------------------
# EC-09: Very long text (3000 chars) → row is valid; full text stored
# ---------------------------------------------------------------------------
def test_ec09_long_text_preserved(tmp_path):
    long_text = "A" * 3000
    csv_path = tmp_path / "long.csv"
    rows = [f"App Store,{r},Title,Review {r} is valid and has enough content for analysis.,{recent_date(r)}"
            for r in range(1, 6)]
    rows.append(f"App Store,3,Long review,{long_text},{recent_date(10)}")
    csv_path.write_text("platform,rating,title,text,date\n" + "\n".join(rows) + "\n", encoding="utf-8")
    reviews, meta = load_reviews(str(csv_path), make_config())
    long_reviews = [r for r in reviews if len(r["text"]) > 2000]
    assert len(long_reviews) == 1
    assert len(long_reviews[0]["text"]) == 3000


# ---------------------------------------------------------------------------
# EC-45: review_window_weeks outside 8–12 — warning logged, no abort
# ---------------------------------------------------------------------------
def test_ec45_out_of_range_window(tmp_path, capsys):
    csv_path = tmp_path / "reviews.csv"
    rows = [f"App Store,{r},Title,Review text that is valid and long enough.,{recent_date(r)}"
            for r in range(1, 8)]
    csv_path.write_text("platform,rating,title,text,date\n" + "\n".join(rows) + "\n", encoding="utf-8")
    # Should not raise
    reviews, meta = load_reviews(str(csv_path), make_config(review_window_weeks=3))
    # Pipeline continues — no SystemExit
    assert isinstance(reviews, list)
