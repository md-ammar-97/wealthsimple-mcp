from __future__ import annotations

from datetime import datetime
from typing import Optional


REQUIRED_COLUMNS = {"platform", "rating", "text", "date"}
ALLOWED_PLATFORMS = {"app store": "App Store", "google play": "Google Play"}


class MissingColumnError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing required columns: {missing}")


def validate_required_columns(df) -> None:
    """Raise MissingColumnError listing all absent required columns."""
    cols = {c.lower().strip() for c in df.columns}
    missing = [req for req in REQUIRED_COLUMNS if req not in cols]
    if missing:
        raise MissingColumnError(missing)


def normalise_platform(val) -> Optional[str]:
    if val is None:
        return None
    normalised = str(val).strip().lower()
    return ALLOWED_PLATFORMS.get(normalised, None)


def parse_date(val) -> Optional[datetime]:
    if val is None or (isinstance(val, float)):
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def validate_rating(val) -> Optional[int]:
    try:
        r = int(float(val))
    except (ValueError, TypeError):
        return None
    return r if 1 <= r <= 5 else None


def validate_text(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if len(s) >= 5 else None
