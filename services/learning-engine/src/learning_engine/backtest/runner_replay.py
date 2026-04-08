from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from learning_engine.backtest.determinism_manifest import build_replay_manifest
from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_backtest
from shared_py.eventbus import EventEnvelope, RedisStreamBus
from shared_py.eventbus.envelope import STREAM_CANDLE_CLOSE, STREAM_MARKET_TICK
from shared_py.model_contracts import FEATURE_SCHEMA_HASH, FEATURE_SCHEMA_VERSION, MODEL_CONTRACT_VERSION
from shared_py.replay_determinism import (
    REPLAY_DETERMINISM_PROTOCOL_VERSION,
    normalized_timeframes,
    stable_replay_session_id,
    stable_stream_event_id,
)

logger = logging.getLogger("learning_engine.backtest.replay")

TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "1H": 3_600_000,
    "4h": 4 * 3_600_000,
    "4H": 4 * 3_600_000,
}


def _tf_ms(tf: str) -> int:
    key = tf.strip()
    if key not in TIMEFRAME_TO_MS:
        raise ValueError(f"unbekanntes timeframe: {tf!r}")
    return TIMEFRAME_TO_MS[key]


def _candle_payload(row: dict[str, Any], *, origin: str) -> dict[str, Any]:
    return {
        "symbol": str(row["symbol"]),
        "timeframe": str(row["timeframe"]),
        "start_ts_ms": int(row["start_ts_ms"]),
        "open": str(row["open"]),
        "high": str(row["high"]),
        "low": str(row["low"]),
        "close": str(row["close"]),
        "base_vol": str(row["base_vol"]),
        "quote_vol": str(row["quote_vol"]),
        "usdt_vol": str(row["usdt_vol"]),
        "origin": origin,
    }


def _minimal_manifest() -> dict[str, Any]:
    return {
        "determinism_protocol_version": REPLAY_DETERMINISM_PROTOCOL_VERSION,
        "model_contract_version": MODEL_CONTRACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "policy_caps": {},
        "note": "Vollstaendiges Manifest: settings= oder determinism_manifest= an run_replay_candles uebergeben.",
    }


def run_replay_candles(
    database_url: str,
    redis_url: str,
    *,
    symbol: str,
    timeframes: list[str],
    from_ts_ms: int,
    to_ts_ms: int,
    speed_factor: float,
    publish_ticks: bool = False,
    chunk_size: int = 500,
    dedupe_prefix: str = "replay",
    ephemeral_session: bool = False,
    settings: LearningEngineSettings | None = None,
    determinism_manifest: dict[str, Any] | None = None,
) -> UUID:
    """Liest tsdb.candles und publiziert events:candle_close chronologisch.

    Standard: deterministische session_id und event_ids (uuid5). Mit ephemeral_session=True
    frische UUIDs (Ad-hoc-Laeufe).
    """
    if speed_factor <= 0:
        raise ValueError("speed_factor muss > 0 sein")
    if from_ts_ms >= to_ts_ms:
        raise ValueError("Zeitraum ungueltig")
    sym = symbol.upper()
    tfs = normalized_timeframes(timeframes)
    if ephemeral_session:
        session_id: UUID = uuid4()
    else:
        session_id = stable_replay_session_id(
            symbol=sym,
            timeframes=tfs,
            from_ts_ms=from_ts_ms,
            to_ts_ms=to_ts_ms,
            speed_factor=speed_factor,
            dedupe_prefix=dedupe_prefix,
            publish_ticks=publish_ticks,
        )
    if determinism_manifest is not None:
        manifest = dict(determinism_manifest)
    elif settings is not None:
        manifest = build_replay_manifest(settings)
    else:
        manifest = _minimal_manifest()
    manifest["replay_session_id"] = str(session_id)
    manifest["symbol"] = sym
    manifest["timeframes"] = tfs
    manifest["from_ts_ms"] = from_ts_ms
    manifest["to_ts_ms"] = to_ts_ms
    manifest["speed_factor"] = float(speed_factor)
    manifest["publish_ticks"] = bool(publish_ticks)
    manifest["dedupe_prefix"] = dedupe_prefix
    manifest["ephemeral_session"] = bool(ephemeral_session)

    bus = RedisStreamBus.from_url(redis_url, dedupe_ttl_sec=0)
    last_event_ts: int | None = None
    trace_base = {
        "source": "learning_engine.replay",
        "session_id": str(session_id),
        "determinism": manifest,
    }

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.transaction():
            repo_backtest.insert_replay_session(
                conn,
                session_id=session_id,
                from_ts_ms=from_ts_ms,
                to_ts_ms=to_ts_ms,
                speed_factor=speed_factor,
                status="running",
                manifest_json=manifest,
            )
        try:
            offset = 0
            total = 0
            while True:
                rows = conn.execute(
                    """
                    SELECT symbol, timeframe, start_ts_ms, open, high, low, close,
                           base_vol, quote_vol, usdt_vol, ingest_ts_ms
                    FROM tsdb.candles
                    WHERE symbol = %s
                      AND timeframe = ANY(%s)
                      AND start_ts_ms >= %s
                      AND start_ts_ms <= %s
                    ORDER BY start_ts_ms ASC, timeframe ASC, ingest_ts_ms ASC
                    LIMIT %s OFFSET %s
                    """,
                    (sym, tfs, from_ts_ms, to_ts_ms, chunk_size, offset),
                ).fetchall()
                if not rows:
                    break
                offset += len(rows)
                for row in rows:
                    row_d = dict(row)
                    tf = str(row_d["timeframe"])
                    start_ms = int(row_d["start_ts_ms"])
                    close_ms = start_ms + _tf_ms(tf)
                    dk = f"{dedupe_prefix}:{sym}:{tf}:{start_ms}"
                    env = EventEnvelope(
                        event_id=stable_stream_event_id(stream=STREAM_CANDLE_CLOSE, dedupe_key=dk),
                        event_type="candle_close",
                        symbol=sym,
                        timeframe=tf,
                        exchange_ts_ms=close_ms,
                        ingest_ts_ms=close_ms,
                        dedupe_key=dk,
                        payload=_candle_payload(row_d, origin="learning_engine.replay"),
                        trace=dict(trace_base),
                    )
                    if last_event_ts is not None:
                        delta_ms = close_ms - last_event_ts
                        if delta_ms > 0:
                            delay_sec = (delta_ms / 1000.0) / speed_factor
                            if 0 < delay_sec < 3600:
                                time.sleep(delay_sec)
                    last_event_ts = close_ms
                    bus.publish(STREAM_CANDLE_CLOSE, env)
                    total += 1
                    if publish_ticks:
                        try:
                            c = Decimal(str(row_d["close"]))
                        except Exception:
                            c = Decimal("0")
                        tdk = f"{dedupe_prefix}:tick:{sym}:{close_ms}:{tf}"
                        tick = EventEnvelope(
                            event_id=stable_stream_event_id(
                                stream=STREAM_MARKET_TICK, dedupe_key=tdk
                            ),
                            event_type="market_tick",
                            symbol=sym,
                            timeframe=tf,
                            exchange_ts_ms=close_ms,
                            ingest_ts_ms=close_ms,
                            dedupe_key=tdk,
                            payload={
                                "symbol": sym,
                                "last_pr": str(c),
                                "bid_pr": str(c),
                                "ask_pr": str(c),
                                "mark_price": str(c),
                                "ts_ms": close_ms,
                                "origin": "learning_engine.replay",
                            },
                            trace=dict(trace_base),
                        )
                        bus.publish(STREAM_MARKET_TICK, tick)
                if len(rows) < chunk_size:
                    break
            logger.info("replay session=%s published_candles=%s", session_id, total)
            with conn.transaction():
                repo_backtest.update_replay_session(conn, session_id=session_id, status="completed")
        except Exception:
            with conn.transaction():
                repo_backtest.update_replay_session(conn, session_id=session_id, status="failed")
            raise
    return session_id
