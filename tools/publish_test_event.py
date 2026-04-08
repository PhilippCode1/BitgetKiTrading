from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _ensure_shared_python_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    shared_src = repo_root / "shared" / "python" / "src"
    shared_src_str = str(shared_src)
    if shared_src.is_dir() and shared_src_str not in sys.path:
        sys.path.insert(0, shared_src_str)


def _load_env_file() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for env_name in (
        ".env.local",
        ".env.shadow",
        ".env.production",
        ".env.test",
        ".env.local.example",
        ".env.shadow.example",
        ".env.production.example",
        ".env.test.example",
    ):
        env_path = repo_root / env_name
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return


def main() -> int:
    _ensure_shared_python_path()
    _load_env_file()

    from shared_py.eventbus import EventEnvelope, RedisStreamBus
    from shared_py.eventbus.envelope import STREAM_CANDLE_CLOSE, STREAM_MARKET_TICK

    bus = RedisStreamBus.from_env()
    now_ms = int(time.time() * 1000)
    candle_start_ms = now_ms - (now_ms % 60_000)
    symbol = os.environ.get("BITGET_SYMBOL", "BTCUSDT")
    candle_close = EventEnvelope(
        event_type="candle_close",
        symbol=symbol,
        timeframe="1m",
        exchange_ts_ms=candle_start_ms + 60_000,
        dedupe_key=f"tools:candle_close:{candle_start_ms}",
        payload={
            "symbol": symbol,
            "timeframe": "1m",
            "start_ts_ms": candle_start_ms,
            "open": "68100.0",
            "high": "68150.0",
            "low": "68090.0",
            "close": "68123.4",
            "base_vol": "12.34",
            "quote_vol": "840000.12",
            "usdt_vol": "840000.12",
            "origin": "tools.publish_test_event",
        },
        trace={"source": "tools.publish_test_event"},
    )
    market_tick = EventEnvelope(
        event_type="market_tick",
        symbol=symbol,
        exchange_ts_ms=now_ms,
        dedupe_key=f"tools:market_tick:{now_ms}",
        payload={
            "symbol": symbol,
            "last_pr": "68123.4",
            "bid_pr": "68123.3",
            "ask_pr": "68123.5",
            "mark_price": "68123.6",
            "index_price": "68121.9",
            "funding_rate": "0.0001",
            "holding_amount": "12345.6789",
            "origin": "tools.publish_test_event",
        },
        trace={"source": "tools.publish_test_event"},
    )

    seeded = _seed_test_candle_history(
        symbol=symbol,
        timeframe="1m",
        candle_start_ms=candle_start_ms,
    )
    if seeded > 0:
        print(f"seeded tsdb.candles rows: {seeded}")
    candle_id = bus.publish(STREAM_CANDLE_CLOSE, candle_close)
    market_tick_id = bus.publish(STREAM_MARKET_TICK, market_tick)
    print(f"published {STREAM_CANDLE_CLOSE}: {candle_id}")
    print(f"published {STREAM_MARKET_TICK}: {market_tick_id}")
    return 0


def _seed_test_candle_history(*, symbol: str, timeframe: str, candle_start_ms: int) -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        return 0
    try:
        import psycopg
    except ImportError:
        print("warning: psycopg nicht installiert, Candle-Seed wird uebersprungen")
        return 0

    rows = _build_seed_rows(symbol=symbol, timeframe=timeframe, candle_start_ms=candle_start_ms)
    sql = """
    INSERT INTO tsdb.candles (
        symbol,
        timeframe,
        start_ts_ms,
        open,
        high,
        low,
        close,
        base_vol,
        quote_vol,
        usdt_vol,
        ingest_ts_ms
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (symbol, timeframe, start_ts_ms) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        base_vol = EXCLUDED.base_vol,
        quote_vol = EXCLUDED.quote_vol,
        usdt_vol = EXCLUDED.usdt_vol,
        ingest_ts_ms = EXCLUDED.ingest_ts_ms
    """
    try:
        with psycopg.connect(database_url, autocommit=True, connect_timeout=5) as conn:
            with conn.transaction():
                conn.executemany(sql, rows)
    except psycopg.Error as exc:
        print(f"warning: Candle-Seed fehlgeschlagen: {exc}")
        return 0
    return len(rows)


def _build_seed_rows(
    *,
    symbol: str,
    timeframe: str,
    candle_start_ms: int,
    count: int = 60,
) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    first_start_ms = candle_start_ms - (count - 1) * 60_000
    ingest_ts_ms = int(time.time() * 1000)
    for index in range(count):
        start_ts_ms = first_start_ms + index * 60_000
        base_price = 68000.0 + index * 1.35
        open_price = base_price + ((index % 4) - 1.5) * 0.18
        close_price = open_price + 0.42 + (index % 3) * 0.07
        high_price = max(open_price, close_price) + 0.33 + (index % 5) * 0.03
        low_price = min(open_price, close_price) - 0.28 - (index % 4) * 0.02
        base_vol = 4.0 + index * 0.08
        usdt_vol = base_vol * close_price
        quote_vol = usdt_vol
        if index == count - 1:
            open_price = 68100.0
            high_price = 68150.0
            low_price = 68090.0
            close_price = 68123.4
            base_vol = 12.34
            quote_vol = 840000.12
            usdt_vol = 840000.12
        rows.append(
            (
                symbol,
                timeframe,
                start_ts_ms,
                str(open_price),
                str(high_price),
                str(low_price),
                str(close_price),
                str(base_vol),
                str(quote_vol),
                str(usdt_vol),
                ingest_ts_ms,
            )
        )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
