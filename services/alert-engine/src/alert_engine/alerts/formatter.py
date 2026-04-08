from __future__ import annotations

import re
from typing import Any


def shorten_url_display(url: str, max_len: int = 48) -> str:
    u = url.strip()
    if len(u) <= max_len:
        return u
    return u[: max_len - 3] + "..."


def truncate_telegram_text(text: str, safe_len: int) -> str:
    """Telegram max 4096 after entity parse; use safe_len (e.g. 3500) as hard cap."""
    t = text.strip()
    if len(t) <= safe_len:
        return t
    return t[: safe_len] + "\n…(truncated)"


def chunk_message(text: str, chunk_size: int) -> list[str]:
    """Split long plain text into chunks <= chunk_size."""
    if len(text) <= chunk_size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + chunk_size])
        start += chunk_size
    return parts


def top_reasons_short(payload: dict[str, Any], n: int = 3) -> list[str]:
    raw = payload.get("reasons_json") or []
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw[:n]:
            if isinstance(item, str):
                s = item.strip()
            elif isinstance(item, dict):
                s = str(item.get("text") or item.get("reason") or item)[:120]
            else:
                s = str(item)[:120]
            if s:
                out.append(s)
    return out


def stop_summary_from_payload(payload: dict[str, Any]) -> str:
    z = payload.get("stop_zone_id")
    if z:
        return f"stop_zone={z}"
    return ""


def escape_for_plain(text: str) -> str:
    """No parse_mode: still strip control chars that could confuse."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
