from __future__ import annotations

import os
import tempfile
import time
import uuid
from multiprocessing import shared_memory
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")

from test_eventbus import StubRedis

from shared_py.eventbus import EventEnvelope
from shared_py.eventbus.envelope import STREAM_MARKET_TICK
from shared_py.eventbus.shared_memory import (
    SharedMemoryBus,
    init_region_mv,
    make_stream_bus_from_url,
    region_size,
)


def _lock_path_for(name: str) -> str:
    return str(Path(tempfile.gettempdir()) / "bgt_eventbus_locks" / f"{name}.lock")


def test_shared_memory_bus_tick_roundtrip() -> None:
    name = f"ut{uuid.uuid4().hex}"
    size = region_size(32, 8192)
    shm = shared_memory.SharedMemory(name=name, create=True, size=size)
    bus_a: SharedMemoryBus | None = None
    bus_b: SharedMemoryBus | None = None
    try:
        mv = memoryview(shm.buf)
        init_region_mv(mv, 32, 8192)
        lock = _lock_path_for(name)
        stub = StubRedis()
        bus_a = SharedMemoryBus(
            redis=stub,
            shm_stream=STREAM_MARKET_TICK,
            _shm=shm,
            _mv=mv,
            _lock_path=lock,
            _slot_count=32,
            _max_payload=8192,
            _shm_publish_spin_max=500,
            _shm_publish_backoff_sec=0.0001,
        )
        env = EventEnvelope(
            event_type="market_tick",
            symbol="BTCUSDT",
            payload={"last_pr": "70000"},
        )
        mid = bus_a.publish(STREAM_MARKET_TICK, env)
        assert mid.startswith("shm-")

        shm_b = shared_memory.SharedMemory(name=name, create=False)
        mv_b = memoryview(shm_b.buf)
        bus_b = SharedMemoryBus(
            redis=stub,
            shm_stream=STREAM_MARKET_TICK,
            _shm=shm_b,
            _mv=mv_b,
            _lock_path=lock,
            _slot_count=32,
            _max_payload=8192,
        )
        deadline = time.perf_counter() + 5.0
        items = []
        while not items and time.perf_counter() < deadline:
            items = bus_b.consume(
                STREAM_MARKET_TICK,
                "g",
                "c",
                count=1,
                block_ms=250,
            )
        assert len(items) == 1
        assert items[0].envelope.event_type == "market_tick"
        assert items[0].envelope.payload["last_pr"] == "70000"
    finally:
        if bus_b is not None:
            bus_b.close()
        if bus_a is not None:
            bus_a.close()
        try:
            u = shared_memory.SharedMemory(name=name, create=False)
        except FileNotFoundError:
            return
        try:
            u.unlink()
        finally:
            u.close()


def test_shared_memory_bus_backpressure_raises() -> None:
    name = f"ut{uuid.uuid4().hex}"
    size = region_size(2, 4096)
    shm = shared_memory.SharedMemory(name=name, create=True, size=size)
    bus: SharedMemoryBus | None = None
    try:
        mv = memoryview(shm.buf)
        init_region_mv(mv, 2, 4096)
        lock = _lock_path_for(name)
        stub = StubRedis()
        bus = SharedMemoryBus(
            redis=stub,
            shm_stream=STREAM_MARKET_TICK,
            _shm=shm,
            _mv=mv,
            _lock_path=lock,
            _slot_count=2,
            _max_payload=4096,
            _shm_publish_spin_max=30,
            _shm_publish_backoff_sec=0.0001,
        )
        env = EventEnvelope(
            event_type="market_tick",
            symbol="BTCUSDT",
            payload={"last_pr": "1"},
        )
        assert bus is not None
        bus.publish(STREAM_MARKET_TICK, env)
        bus.publish(STREAM_MARKET_TICK, env)
        with pytest.raises(ValueError, match="shm_ring_voll"):
            bus.publish(STREAM_MARKET_TICK, env)
    finally:
        if bus is not None:
            bus.close()
        try:
            u = shared_memory.SharedMemory(name=name, create=False)
            u.unlink()
            u.close()
        except FileNotFoundError:
            pass


def test_make_stream_bus_fallback_without_env() -> None:
    from unittest.mock import patch

    from redis import Redis

    from shared_py.eventbus.redis_streams import RedisStreamBus

    os.environ.pop("USE_SHARED_MEMORY", None)
    with patch.object(Redis, "from_url", return_value=StubRedis()):
        bus = make_stream_bus_from_url("redis://noop")
    assert isinstance(bus, RedisStreamBus)
    bus.close()
