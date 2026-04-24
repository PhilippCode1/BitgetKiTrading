"""Shared-Memory Eventbus (Arrow IPC Nutzlast) — kompatibel zu `RedisStreamBus`.

Layout-Version und Konstanten sind an `shared_rs/shm_ring` angeglichen.
Zwischen Prozessen wird ein Datei-Lock genutzt (POSIX `flock`, Windows `msvcrt`);
der Hot-Path serialisiert damit — korrekt, aber nicht lock-frei (siehe Rust-Crate
für lock-freie Referenz).
"""

from __future__ import annotations

import errno
import json
import logging
import os
import struct
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from redis import Redis

from .canonical import event_envelope_to_canonical_json_text
from .envelope import EVENT_STREAMS, STREAM_DLQ, STREAM_MARKET_TICK, EventEnvelope
from .redis_streams import ConsumedEvent, RedisStreamBus

_LOG = logging.getLogger(__name__)

MAGIC: Final[int] = 0x42_47_54_5F_53_48_4D_51
VERSION: Final[int] = 1
HEADER_SIZE: Final[int] = 128
LAYOUT_VERSION: Final[int] = 1

_OFF_MAGIC: Final[int] = 0
_OFF_VERSION: Final[int] = 8
_OFF_SLOT_COUNT: Final[int] = 12
_OFF_SLOT_STRIDE: Final[int] = 16
_OFF_MAX_PAYLOAD: Final[int] = 20
_OFF_HEAD: Final[int] = 64
_OFF_TAIL: Final[int] = 72


def slot_stride(max_payload: int) -> int:
    body = 8 + int(max_payload)
    return (body + 7) & ~7


def region_size(slot_count: int, max_payload: int) -> int:
    stride = slot_stride(max_payload)
    return HEADER_SIZE + int(slot_count) * stride


def _sanitize_shm_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in "._-")
    return (cleaned or "bgt_eventbus")[:200]


class _CrossProcessFileLock:
    """Exklusives Byte-0-Lock auf einer Lock-Datei (blockierend)."""

    __slots__ = ("_fd", "_path")

    def __init__(self, path: str) -> None:
        self._path = path
        self._fd: int | None = None

    def __enter__(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        if sys.platform == "win32":
            import msvcrt

            os.lseek(self._fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.0005)
        else:
            import fcntl

            fcntl.flock(self._fd, fcntl.LOCK_EX)

    def __exit__(self, *exc: object) -> None:
        if self._fd is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                os.lseek(self._fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None


def _validate_stream_name(stream: str) -> None:
    if stream not in EVENT_STREAMS:
        raise ValueError(f"ungueltiger Stream-Name: {stream}")


def init_region_mv(buf: memoryview, slot_count: int, max_payload: int) -> None:
    if slot_count <= 0:
        raise ValueError("slot_count")
    stride = slot_stride(max_payload)
    need = region_size(slot_count, max_payload)
    if len(buf) < need:
        raise ValueError("buffer zu klein")
    buf[:need].cast("B")[:] = b"\x00" * need
    struct.pack_into("<Q", buf, _OFF_MAGIC, MAGIC)
    struct.pack_into("<I", buf, _OFF_VERSION, VERSION)
    struct.pack_into("<I", buf, _OFF_SLOT_COUNT, slot_count)
    struct.pack_into("<I", buf, _OFF_SLOT_STRIDE, stride)
    struct.pack_into("<I", buf, _OFF_MAX_PAYLOAD, max_payload)
    struct.pack_into("<I", buf, 24, LAYOUT_VERSION)
    struct.pack_into("<QQ", buf, _OFF_HEAD, 0, 0)


def load_meta_mv(buf: memoryview) -> tuple[int, int, int]:
    if len(buf) < HEADER_SIZE:
        raise ValueError("header")
    magic = struct.unpack_from("<Q", buf, _OFF_MAGIC)[0]
    if magic != MAGIC:
        raise ValueError("magic")
    ver = struct.unpack_from("<I", buf, _OFF_VERSION)[0]
    if ver != VERSION:
        raise ValueError("version")
    slot_count = struct.unpack_from("<I", buf, _OFF_SLOT_COUNT)[0]
    stride = struct.unpack_from("<I", buf, _OFF_SLOT_STRIDE)[0]
    max_payload = struct.unpack_from("<I", buf, _OFF_MAX_PAYLOAD)[0]
    if slot_count == 0 or stride < 8:
        raise ValueError("meta")
    return int(slot_count), int(stride), int(max_payload)


def _try_publish_locked(buf: memoryview, payload: bytes) -> int | None:
    slot_count, stride, max_payload = load_meta_mv(buf)
    if len(payload) > max_payload:
        raise ValueError("payload zu gross")
    n = slot_count
    t = struct.unpack_from("<Q", buf, _OFF_TAIL)[0]
    h = struct.unpack_from("<Q", buf, _OFF_HEAD)[0]
    if t - h >= n:
        return None
    idx = int(t % n)
    sb = HEADER_SIZE + idx * stride
    state = struct.unpack_from("<I", buf, sb)[0]
    if state != 0:
        raise RuntimeError("slot nicht leer")
    struct.pack_into("<I", buf, sb + 4, len(payload))
    buf[sb + 8 : sb + 8 + len(payload)] = payload
    struct.pack_into("<I", buf, sb, 1)
    struct.pack_into("<Q", buf, _OFF_TAIL, t + 1)
    return int(t)


def _try_consume_locked(buf: memoryview) -> tuple[int, bytes] | None:
    slot_count, stride, max_payload = load_meta_mv(buf)
    n = slot_count
    h = struct.unpack_from("<Q", buf, _OFF_HEAD)[0]
    t = struct.unpack_from("<Q", buf, _OFF_TAIL)[0]
    if t == h:
        return None
    idx = int(h % n)
    sb = HEADER_SIZE + idx * stride
    if struct.unpack_from("<I", buf, sb)[0] != 1:
        return None
    ln = struct.unpack_from("<I", buf, sb + 4)[0]
    if ln > max_payload:
        raise ValueError("korrupt")
    data = bytes(buf[sb + 8 : sb + 8 + ln])
    struct.pack_into("<I", buf, sb, 0)
    struct.pack_into("<Q", buf, _OFF_HEAD, h + 1)
    return int(h), data


def _arrow_encode_stream_envelope(stream: str, env: EventEnvelope) -> bytes:
    import pyarrow as pa
    from pyarrow import ipc

    schema = pa.schema(
        [
            ("stream", pa.string()),
            ("envelope_bin", pa.large_binary()),
        ]
    )
    raw = event_envelope_to_canonical_json_text(env).encode("utf-8")
    batch = pa.record_batch(
        {"stream": pa.array([stream], type=pa.string()), "envelope_bin": pa.array([raw])},
        schema=schema,
    )
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, batch.schema) as writer:
        writer.write_batch(batch)
    return sink.getvalue().to_pybytes()


def _arrow_decode_stream_envelope(blob: bytes) -> tuple[str, EventEnvelope]:
    import pyarrow as pa
    from pyarrow import ipc

    reader = ipc.open_stream(pa.BufferReader(blob))
    batch = reader.read_next_batch()
    if batch is None or batch.num_rows == 0:
        raise ValueError("leerer Arrow-IPC Batch")
    stream = batch.column(0)[0].as_py()
    raw = batch.column(1)[0].as_py()
    if not isinstance(stream, str) or not isinstance(raw, (bytes, memoryview)):
        raise ValueError("unexpected Arrow columns")
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    return stream, EventEnvelope.model_validate_json(raw.decode("utf-8"))


def _normalize_original_payload(original: Any) -> dict[str, Any]:
    if isinstance(original, EventEnvelope):
        return original.model_dump(mode="json")
    if isinstance(original, dict):
        return json.loads(json.dumps(original, default=str))
    return {"raw": str(original)}


def _build_dlq_dedupe_key(payload: dict[str, Any]) -> str | None:
    event_id = payload.get("event_id")
    if event_id is None:
        return None
    return f"dlq:{event_id}"


@dataclass
class SharedMemoryBus:
    """Gleiches öffentliches API wie `RedisStreamBus`; Tick-Pfad über SHM + Arrow."""

    redis: Redis
    shm_stream: str
    dedupe_ttl_sec: int = 0
    default_block_ms: int = 2000
    default_count: int = 50
    _shm: Any = field(repr=False, default=None)
    _mv: memoryview | None = field(repr=False, default=None)
    _lock_path: str = field(repr=False, default="")
    _slot_count: int = field(repr=False, default=4096)
    _max_payload: int = field(repr=False, default=65536)
    _shm_publish_spin_max: int = field(repr=False, default=5000)
    _shm_publish_backoff_sec: float = field(repr=False, default=0.001)

    @classmethod
    def from_env(cls) -> SharedMemoryBus:
        return cls.from_url(os.environ["REDIS_URL"])

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        dedupe_ttl_sec: int = 0,
        default_block_ms: int = 2000,
        default_count: int = 50,
    ) -> SharedMemoryBus:
        from multiprocessing import shared_memory

        redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        shm_name = _sanitize_shm_name(os.environ.get("EVENTBUS_SHM_NAME", "bgt_eventbus"))
        slot_count = max(1, int(os.environ.get("EVENTBUS_SHM_SLOTS", "4096")))
        max_payload = max(64, int(os.environ.get("EVENTBUS_SHM_MAX_PAYLOAD", "65536")))
        shm_stream = (
            os.environ.get("EVENTBUS_SHM_STREAM", STREAM_MARKET_TICK).strip() or STREAM_MARKET_TICK
        )
        lock_path = str(
            Path(tempfile.gettempdir()) / "bgt_eventbus_locks" / f"{shm_name}.lock"
        )
        spin_max = max(1, int(os.environ.get("EVENTBUS_SHM_PUBLISH_SPIN_MAX", "5000")))
        backoff = float(os.environ.get("EVENTBUS_SHM_PUBLISH_BACKOFF_SEC", "0.001"))

        size = region_size(slot_count, max_payload)
        creator = False
        try:
            shm = shared_memory.SharedMemory(name=shm_name, create=True, size=size)
            creator = True
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=shm_name, create=False)
        except OSError as exc:
            exists = exc.errno == errno.EEXIST or getattr(exc, "winerror", None) == 183
            if not exists:
                raise
            shm = shared_memory.SharedMemory(name=shm_name, create=False)
        mv = memoryview(shm.buf)
        if creator:
            init_region_mv(mv, slot_count, max_payload)
        else:
            sc, _, mp = load_meta_mv(mv)
            need_existing = region_size(sc, mp)
            if len(mv) < need_existing:
                mv.release()
                shm.close()
                raise ValueError("SHM-Segment zu klein fuer Metadaten")
            if sc != slot_count or mp != max_payload:
                mv.release()
                shm.close()
                raise ValueError(
                    "EVENTBUS_SHM_SLOTS/MAX_PAYLOAD passen nicht zum bestehenden Segment"
                )
        if creator:
            _LOG.info(
                "SharedMemoryBus Segment erstellt name=%s slots=%s max_payload=%s stream=%s",
                shm_name,
                slot_count,
                max_payload,
                shm_stream,
            )
        return cls(
            redis=redis_client,
            shm_stream=shm_stream,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
            _shm=shm,
            _mv=mv,
            _lock_path=lock_path,
            _slot_count=slot_count,
            _max_payload=max_payload,
            _shm_publish_spin_max=spin_max,
            _shm_publish_backoff_sec=backoff,
        )

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def close(self) -> None:
        if self._mv is not None:
            try:
                self._mv.release()
            finally:
                self._mv = None
        if self._shm is not None:
            try:
                self._shm.close()
            finally:
                self._shm = None
        self.redis.close()

    def publish(self, stream: str, env: EventEnvelope) -> str:
        _validate_stream_name(stream)
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
        if stream == self.shm_stream and self._mv is not None:
            payload = _arrow_encode_stream_envelope(stream, env)
            for _ in range(self._shm_publish_spin_max):
                with _CrossProcessFileLock(self._lock_path):
                    assert self._mv is not None
                    seq = _try_publish_locked(self._mv, payload)
                if seq is not None:
                    return f"shm-{seq}"
                time.sleep(self._shm_publish_backoff_sec)
            raise ValueError("shm_ring_voll")
        return str(self.redis.xadd(stream, {"data": event_envelope_to_canonical_json_text(env)}))

    def ensure_group(self, stream: str, group: str) -> None:
        _validate_stream_name(stream)
        try:
            self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as exc:  # pragma: no cover
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
        _validate_stream_name(stream)
        if stream == self.shm_stream and self._mv is not None:
            return self._consume_shm(stream, count, block_ms)
        items = self.redis.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=count or self.default_count,
            block=block_ms or self.default_block_ms,
        )
        return self._redis_messages_to_consumed(group, items)

    def _consume_shm(
        self, stream: str, count: int | None, block_ms: int | None
    ) -> list[ConsumedEvent]:
        assert self._mv is not None
        deadline = time.monotonic() + (block_ms or self.default_block_ms) / 1000.0
        limit = count or self.default_count
        out: list[ConsumedEvent] = []
        while time.monotonic() < deadline and len(out) < limit:
            with _CrossProcessFileLock(self._lock_path):
                got = _try_consume_locked(self._mv)
            if got is None:
                time.sleep(0.001)
                continue
            seq, blob = got
            try:
                dst, envelope = _arrow_decode_stream_envelope(blob)
            except Exception as exc:
                self.publish_dlq(
                    {
                        "stream": stream,
                        "message_id": f"shm-{seq}",
                        "fields": {"raw_len": len(blob)},
                    },
                    {"stage": "consume_shm", "error": str(exc)},
                )
                continue
            if dst != stream:
                self.publish_dlq(
                    {
                        "stream": stream,
                        "message_id": f"shm-{seq}",
                        "fields": {"decoded_stream": dst},
                    },
                    {"stage": "consume_shm", "error": "stream_mismatch"},
                )
                continue
            out.append(
                ConsumedEvent(stream=stream, message_id=f"shm-{seq}", envelope=envelope)
            )
        return out

    def _redis_messages_to_consumed(
        self, group: str, items: list[tuple[str, list[tuple[str, dict[str, str]]]]]
    ) -> list[ConsumedEvent]:
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
                        {"stage": "consume", "error": str(exc)},
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
        _validate_stream_name(stream)
        if message_id.startswith("shm-"):
            return 1
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
                "source": "shared_memory_bus",
                "original_event_type": original_payload.get("event_type"),
            },
        )
        if envelope.dedupe_key and self.dedupe_ttl_sec > 0:
            key = f"dedupe:{STREAM_DLQ}:{envelope.dedupe_key}"
            if self.redis.set(key, "1", nx=True, ex=self.dedupe_ttl_sec) is None:
                return "deduped"
        return str(self.redis.xadd(STREAM_DLQ, {"data": event_envelope_to_canonical_json_text(envelope)}))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value))


def make_stream_bus_from_url(
    redis_url: str,
    *,
    dedupe_ttl_sec: int = 0,
    default_block_ms: int = 2000,
    default_count: int = 50,
    logger: logging.Logger | None = None,
) -> RedisStreamBus | SharedMemoryBus:
    """Wählt bei ``USE_SHARED_MEMORY=true`` den SHM-Bus, sonst Redis; Fallback bei Fehlern."""
    log = logger or _LOG
    use = os.environ.get("USE_SHARED_MEMORY", "").lower() in {"1", "true", "yes", "on"}
    if not use:
        return RedisStreamBus.from_url(
            redis_url,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
        )
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        log.warning("pyarrow fehlt, Fallback auf RedisStreamBus")
        return RedisStreamBus.from_url(
            redis_url,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
        )
    try:
        bus = SharedMemoryBus.from_url(
            redis_url,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
        )
        bus.ping()
        log.info("Eventbus: SharedMemoryBus aktiv (USE_SHARED_MEMORY)")
        return bus
    except Exception as exc:
        if log.isEnabledFor(logging.DEBUG):
            log.warning(
                "SharedMemoryBus nicht verfuegbar (%s), Fallback auf RedisStreamBus",
                exc,
                exc_info=True,
            )
        else:
            log.warning(
                "SharedMemoryBus nicht verfuegbar (%s), Fallback auf RedisStreamBus",
                exc,
            )
        return RedisStreamBus.from_url(
            redis_url,
            dedupe_ttl_sec=dedupe_ttl_sec,
            default_block_ms=default_block_ms,
            default_count=default_count,
        )
