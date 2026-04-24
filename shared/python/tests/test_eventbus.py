from __future__ import annotations

from shared_py.eventbus import EventEnvelope, RedisStreamBus
from shared_py.eventbus.envelope import STREAM_CANDLE_CLOSE, STREAM_DLQ, STREAM_MARKET_TICK


class StubRedis:
    def __init__(self) -> None:
        self._streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._dedupe_keys: set[str] = set()
        self._groups: set[tuple[str, str]] = set()
        self._acks: list[tuple[str, str, str]] = []
        self._counter = 0

    def close(self) -> None:
        return

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        del value, ex
        if nx and key in self._dedupe_keys:
            return None
        self._dedupe_keys.add(key)
        return True

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self._counter += 1
        message_id = f"{self._counter}-0"
        self._streams.setdefault(stream, []).append((message_id, fields))
        return message_id

    def xgroup_create(self, stream: str, group: str, id: str = "0", mkstream: bool = True) -> bool:
        del id
        if (stream, group) in self._groups:
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        self._groups.add((stream, group))
        if mkstream:
            self._streams.setdefault(stream, [])
        return True

    def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        count: int,
        block: int,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        del group, consumer, block
        stream, _last_id = next(iter(streams.items()))
        return [(stream, self._streams.get(stream, [])[:count])]

    def xack(self, stream: str, group: str, message_id: str) -> int:
        self._acks.append((stream, group, message_id))
        return 1

    def xlen(self, stream: str) -> int:
        return len(self._streams.get(stream, []))

    def xrevrange(
        self,
        stream: str,
        max: str = "+",
        min: str = "-",
        count: int = 10,
    ) -> list[tuple[str, dict[str, str]]]:
        del max, min
        return list(reversed(self._streams.get(stream, [])))[:count]


def test_publish_dedupes_same_candle_close_event() -> None:
    bus = RedisStreamBus(redis=StubRedis(), dedupe_ttl_sec=60)
    envelope = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        timeframe="1m",
        exchange_ts_ms=1_700_000_060_000,
        dedupe_key="BTCUSDT:1m:1700000000000",
        payload={
            "start_ts_ms": 1_700_000_000_000,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 68123.4,
        },
    )

    first = bus.publish(STREAM_CANDLE_CLOSE, envelope)
    second = bus.publish(STREAM_CANDLE_CLOSE, envelope)

    assert first != "deduped"
    assert second == "deduped"


def test_publish_dlq_wraps_original_event() -> None:
    redis = StubRedis()
    bus = RedisStreamBus(redis=redis, dedupe_ttl_sec=60)
    original = EventEnvelope(
        event_type="market_tick",
        symbol="BTCUSDT",
        payload={"last_pr": "68123.4"},
    )

    message_id = bus.publish_dlq(original, {"stage": "publish", "error": "boom"})

    assert message_id != "deduped"
    assert redis.xlen(STREAM_DLQ) == 1
    dlq_payload = redis.xrevrange(STREAM_DLQ, count=1)[0][1]["data"]
    assert "\"event_type\":\"dlq\"" in dlq_payload
    assert "\"original_event_type\":\"market_tick\"" in dlq_payload


def test_consume_parses_envelopes_and_acks_invalid_entries() -> None:
    redis = StubRedis()
    bus = RedisStreamBus(redis=redis, dedupe_ttl_sec=60, default_count=10)
    bus.ensure_group(STREAM_MARKET_TICK, "test-group")
    valid = EventEnvelope(
        event_type="market_tick",
        symbol="BTCUSDT",
        payload={"last_pr": "68123.4"},
    )
    redis.xadd(STREAM_MARKET_TICK, {"data": valid.model_dump_json()})
    redis.xadd(STREAM_MARKET_TICK, {"data": "{\"bad\":true}"})

    consumed = bus.consume(
        STREAM_MARKET_TICK,
        group="test-group",
        consumer="consumer-1",
    )

    assert len(consumed) == 1
    assert consumed[0].envelope.event_type == "market_tick"
    assert redis._acks == [(STREAM_MARKET_TICK, "test-group", "2-0")]
    assert redis.xlen(STREAM_DLQ) == 1
