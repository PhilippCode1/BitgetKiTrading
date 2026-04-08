from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_iso_to_ms(value: str | None) -> int | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_rss_pub_date(value: str | None) -> int | None:
    if not value or not str(value).strip():
        return None
    try:
        dt = parsedate_to_datetime(str(value).strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_gdelt_seendate(value: str | None) -> int | None:
    if not value or len(str(value)) < 14:
        return None
    try:
        dt = datetime.strptime(str(value)[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)
