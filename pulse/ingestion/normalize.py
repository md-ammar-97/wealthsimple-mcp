"""
Normalize reviews_raw.csv → reviews_clean.csv.

Filters applied (in order):
  1. Drop rows where text has fewer than 8 words
  2. Drop rows whose title or text contains any emoji character
  3. Drop rows not detected as English (langdetect)

Output columns are identical to input; no content is altered.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

try:
    from langdetect import detect, LangDetectException  # type: ignore
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

# All major Unicode emoji blocks
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F300-\U0001F5FF"   # misc symbols & pictographs
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F700-\U0001F77F"   # alchemical symbols
    "\U0001F780-\U0001F7FF"   # geometric shapes extended
    "\U0001F800-\U0001F8FF"   # supplemental arrows-C
    "\U0001F900-\U0001F9FF"   # supplemental symbols & pictographs
    "\U0001FA00-\U0001FA6F"   # chess symbols
    "\U0001FA70-\U0001FAFF"   # symbols & pictographs extended-A
    "\U00002600-\U000026FF"   # misc symbols
    "\U00002700-\U000027BF"   # dingbats
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U0001F1E0-\U0001F1FF"   # regional indicator (flags)
    "]+",
    flags=re.UNICODE,
)

NORMALIZED_FIELDNAMES = [
    "platform", "rating", "title", "text", "date",
    "app_version", "country", "helpful_votes",
]


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def _word_count(text: str) -> int:
    return len(text.split())


def _is_english(text: str) -> bool:
    if not _LANGDETECT_AVAILABLE:
        return True
    try:
        return detect(text) == "en"
    except LangDetectException:
        return False


def normalize_reviews(raw_path: str, clean_path: str) -> dict:
    """
    Read reviews_raw.csv, apply filters, write reviews_clean.csv.

    Returns a stats dict with counts for each filter stage.
    """
    raw = Path(raw_path)
    out = Path(clean_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    dropped_short = 0
    dropped_emoji = 0
    dropped_lang = 0
    kept_rows: list[dict] = []

    with open(raw, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            text = (row.get("text") or "").strip()
            title = (row.get("title") or "").strip()

            if _word_count(text) < 8:
                dropped_short += 1
                continue

            if _has_emoji(text) or _has_emoji(title):
                dropped_emoji += 1
                continue

            if not _is_english(text):
                dropped_lang += 1
                continue

            kept_rows.append({k: row.get(k, "") for k in NORMALIZED_FIELDNAMES})

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NORMALIZED_FIELDNAMES)
        writer.writeheader()
        writer.writerows(kept_rows)

    stats = {
        "total_raw": total,
        "kept": len(kept_rows),
        "dropped_short_text": dropped_short,
        "dropped_emoji": dropped_emoji,
        "dropped_non_english": dropped_lang,
    }

    print(
        f"  Normalize: {total} raw -> {len(kept_rows)} kept "
        f"(dropped {dropped_short} short, {dropped_emoji} emoji, {dropped_lang} non-English)"
    )
    return stats


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

    raw = str(project_root / "data" / "input" / "reviews_raw.csv")
    clean = str(project_root / "data" / "output" / "reviews_clean.csv")
    normalize_reviews(raw, clean)
