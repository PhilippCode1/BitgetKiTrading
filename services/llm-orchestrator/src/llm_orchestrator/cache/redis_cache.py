from __future__ import annotations

import hashlib
import json
from typing import Any

from redis import Redis


def stable_json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_key(*, provider: str, model: str, schema_hash: str, input_hash: str) -> str:
    safe_model = model.replace(" ", "_")[:80]
    return f"llm:{provider}:{safe_model}:{schema_hash}:{input_hash}"


class LLMRedisCache:
    def __init__(self, redis: Redis, *, ttl_sec: int) -> None:
        self._r = redis
        self._ttl = ttl_sec

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self._r.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        self._r.setex(key, self._ttl, payload)
