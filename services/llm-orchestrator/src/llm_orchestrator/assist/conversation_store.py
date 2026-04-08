from __future__ import annotations

import json
import re

from redis import Redis

_RE_SAFE_PART = re.compile(r"[^a-zA-Z0-9_.-]+")


def _sanitize_partition(segment: str) -> str:
    t = (segment or "").strip()
    if not t:
        return "anon"
    s = _RE_SAFE_PART.sub("_", t)[:200]
    return s or "anon"


class AssistConversationStore:
    """Redis-gestuetzte Kurzhistorie fuer mehrstufige Assistenz (kein Trade-State)."""

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_sec: int,
        max_messages: int,
        key_prefix: str = "llm:assist:v1",
    ) -> None:
        self._r = redis
        self._ttl = max(60, ttl_sec)
        self._max = max(2, min(max_messages, 200))
        self._prefix = key_prefix

    def _key(
        self, partition_id: str, assist_role: str, conversation_id: str
    ) -> str:
        rp = _sanitize_partition(partition_id)
        rr = _sanitize_partition(assist_role)
        return f"{self._prefix}:{rp}:{rr}:{conversation_id}"

    def load_history(
        self,
        *,
        partition_id: str,
        assist_role: str,
        conversation_id: str,
    ) -> list[dict[str, str]]:
        raw = self._r.get(self._key(partition_id, assist_role, conversation_id))
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        out: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            content = str(item.get("content_de") or "")
            if role not in ("user", "assistant") or not content:
                continue
            out.append({"role": role, "content_de": content})
        return out[-self._max :]

    def save_history(
        self,
        *,
        partition_id: str,
        assist_role: str,
        conversation_id: str,
        messages: list[dict[str, str]],
    ) -> None:
        trimmed = messages[-self._max :]
        payload = json.dumps(trimmed, ensure_ascii=False)
        self._r.setex(
            self._key(partition_id, assist_role, conversation_id),
            self._ttl,
            payload,
        )

    def append_exchange(
        self,
        *,
        partition_id: str,
        assist_role: str,
        conversation_id: str,
        user_message_de: str,
        assistant_reply_de: str,
    ) -> list[dict[str, str]]:
        hist = self.load_history(
            partition_id=partition_id,
            assist_role=assist_role,
            conversation_id=conversation_id,
        )
        hist.append({"role": "user", "content_de": user_message_de})
        hist.append({"role": "assistant", "content_de": assistant_reply_de})
        self.save_history(
            partition_id=partition_id,
            assist_role=assist_role,
            conversation_id=conversation_id,
            messages=hist,
        )
        return hist
