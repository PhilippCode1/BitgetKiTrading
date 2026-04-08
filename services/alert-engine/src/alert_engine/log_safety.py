from __future__ import annotations

import hashlib
from typing import Any


def _short_hash(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "unknown"
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
    return digest[:10]


def safe_chat_ref(chat_id: Any) -> str:
    return f"chat:{_short_hash(chat_id)}"


def safe_user_ref(user_id: Any) -> str:
    return f"user:{_short_hash(user_id)}"


def safe_key_ref(value: Any) -> str:
    return f"key:{_short_hash(value)}"
