from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from redis import Redis

from .envelope import EVENT_STREAMS, EventEnvelope, STREAM_DLQ


@dataclass(frozen=True)
class ConsumedEvent:
    stream: str
    message_id: str
    envelope: EventEnvelope


@dataclass(frozen=True)
class RedisStreamBus:
    redis: Redis
    dedupe_ttl_sec: int = 0
    default_block_ms: int = 2000
    default_count: int = 50

    @classmethod
    def from_env(cls) -> "RedisStreamBus":
        url = os.environ["REDIS_URL"]
        ttl = int(os.environ.get("EVENTBUS_DEDUPE_TTL_SEC", "0"))
        block_ms = int(os.environ.get("EVENTBUS_DEFAULT_BLOCK_MS", "2000"))
        count = int(os.environ.get("EVENTBUS_DEFAULT_COUNT", "50"))
        redis_client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        return cls(
            redis=redis_client,
            dedupe_ttl_sec=ttl,
            default_block_ms=block_ms,
            default_count=count,
        )

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        dedupe_ttl_sec: int = 0,
        default_block_ms: int = 2000,
        default_count: int = 50,
    ) -> "RedisStreamBus":
        redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        return cls(
            redis=redis_client,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
        )

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def close(self) -> None:
        self.redis.close()

    def publish(self, stream: str, env: EventEnvelope) -> str:
        _validate_stream(stream)
        expected_stream = env.default_stream()
        if stream != expected_stream:
            raise ValueError(
                f"event_type={env.event_type} darf nicht auf {stream} publiziert werden "
                f"(erwartet {expected_stream})"
            )
        if env.dedupe_key and self.dedupe_ttl_sec > 0:
            key = f"dedupe:{stream}:{env.dedupe_key}"
            if self.redis.set(key, "1", nx=True, ex=self.dedupe_ttl_sec) is None:
                return "deduped"
        return str(self.redis.xadd(stream, {"data": env.model_dump_json()}))

    def ensure_group(self, stream: str, group: str) -> None:
        _validate_stream(stream)
        try:
            self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as exc:  # pragma: no cover - real redis branch
            if "BUSYGROUP" in str(exc):
                return
            raise

    def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int | None = None,
        block_ms: int | None = None,
    ) -> list[ConsumedEvent]:
        _validate_stream(stream)
        items = self.redis.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=count or self.default_count,
            block=block_ms or self.default_block_ms,
        )
        consumed: list[ConsumedEvent] = []
        for stream_name, messages in items:
            for message_id, fields in messages:
                raw_payload = fields.get("data", "")
                try:
                    envelope = EventEnvelope.model_validate_json(raw_payload)
                except Exception as exc:
                    self.publish_dlq(
                        {
                            "stream": stream_name,
                            "message_id": message_id,
                            "fields": fields,
                        },
                        {
                            "stage": "consume",
                            "error": str(exc),
                        },
                    )
                    self.ack(stream_name, group, message_id)
                    continue
                consumed.append(
                    ConsumedEvent(
                        stream=stream_name,
                        message_id=message_id,
                        envelope=envelope,
                    )
                )
        return consumed

    def ack(self, stream: str, group: str, message_id: str) -> int:
        _validate_stream(stream)
        return int(self.redis.xack(stream, group, message_id))

    def publish_dlq(self, original: Any, error_info: dict[str, Any]) -> str:
        original_payload = _normalize_original_payload(original)
        envelope = EventEnvelope(
            event_type="dlq",
            symbol=str(original_payload.get("symbol") or "UNKNOWN"),
            timeframe=_optional_str(original_payload.get("timeframe")),
            exchange_ts_ms=_optional_int(original_payload.get("exchange_ts_ms")),
            dedupe_key=_build_dlq_dedupe_key(original_payload),
            payload={
                "original": original_payload,
                "error": error_info,
            },
            trace={
                "source": "redis_stream_bus",
                "original_event_type": original_payload.get("event_type"),
            },
        )
        if envelope.dedupe_key and self.dedupe_ttl_sec > 0:
            key = f"dedupe:{STREAM_DLQ}:{envelope.dedupe_key}"
            if self.redis.set(key, "1", nx=True, ex=self.dedupe_ttl_sec) is None:
                return "deduped"
        return str(self.redis.xadd(STREAM_DLQ, {"data": envelope.model_dump_json()}))


def _validate_stream(stream: str) -> None:
    if stream not in EVENT_STREAMS:
        raise ValueError(f"ungueltiger Stream-Name: {stream}")


def _normalize_original_payload(original: Any) -> dict[str, Any]:
    if isinstance(original, EventEnvelope):
        return original.model_dump(mode="json")
    if isinstance(original, dict):
        return _json_safe_dict(original)
    return {"raw": str(original)}


def _json_safe_dict(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, default=str))


def _build_dlq_dedupe_key(payload: dict[str, Any]) -> str | None:
    event_id = payload.get("event_id")
    if event_id is None:
        return None
    return f"dlq:{event_id}"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value))
