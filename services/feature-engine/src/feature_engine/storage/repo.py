from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Sequence

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class StoredCandle:
    symbol: str
    timeframe: str
    start_ts_ms: int
    o: float
    h: float
    l: float
    c: float
    base_vol: float
    quote_vol: float
    usdt_vol: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    ts_ms: int
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]
    source: str = "orderbook_levels"


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    ts_ms: int
    source: str
    bid_pr: float | None
    ask_pr: float | None
    bid_sz: float | None
    ask_sz: float | None
    last_pr: float | None
    mark_price: float | None
    index_price: float | None


@dataclass(frozen=True)
class FundingSnapshot:
    symbol: str
    ts_ms: int
    source: str
    funding_rate: float
    interval_hours: int | None
    next_update_ms: int | None


@dataclass(frozen=True)
class OpenInterestSnapshot:
    symbol: str
    ts_ms: int
    source: str
    size: float


@dataclass(frozen=True)
class CandleFeatureRow:
    feature_schema_version: str
    feature_schema_hash: str
    canonical_instrument_id: str
    market_family: str
    product_type: str | None
    margin_account_mode: str | None
    instrument_metadata_snapshot_id: str | None
    symbol: str
    timeframe: str
    start_ts_ms: int
    atr_14: float | None
    atrp_14: float | None
    rsi_14: float | None
    ret_1: float | None
    ret_5: float | None
    momentum_score: float | None
    impulse_body_ratio: float | None
    impulse_upper_wick_ratio: float | None
    impulse_lower_wick_ratio: float | None
    range_score: float | None
    trend_ema_fast: float | None
    trend_ema_slow: float | None
    trend_slope_proxy: float | None
    trend_dir: int
    confluence_score_0_100: float | None
    vol_z_50: float | None
    spread_bps: float | None
    bid_depth_usdt_top25: float | None
    ask_depth_usdt_top25: float | None
    orderbook_imbalance: float | None
    depth_balance_ratio: float | None
    depth_to_bar_volume_ratio: float | None
    impact_buy_bps_5000: float | None
    impact_sell_bps_5000: float | None
    impact_buy_bps_10000: float | None
    impact_sell_bps_10000: float | None
    execution_cost_bps: float | None
    volatility_cost_bps: float | None
    funding_rate: float | None
    funding_rate_bps: float | None
    funding_cost_bps_window: float | None
    funding_time_to_next_ms: int | None
    open_interest: float | None
    open_interest_change_pct: float | None
    mark_index_spread_bps: float | None
    basis_bps: float | None
    session_drift_bps: float | None
    spread_persistence_bps: float | None
    mean_reversion_pressure_0_100: float | None
    breakout_compression_score_0_100: float | None
    realized_vol_cluster_0_100: float | None
    liquidation_distance_bps_max_leverage: float | None
    data_completeness_0_1: float | None
    staleness_score_0_1: float | None
    gap_count_lookback: int | None
    event_distance_ms: int | None
    feature_quality_status: str | None
    orderbook_age_ms: int | None
    funding_age_ms: int | None
    open_interest_age_ms: int | None
    liquidity_source: str | None
    funding_source: str | None
    open_interest_source: str | None
    source_event_id: str
    computed_ts_ms: int
    input_provenance: dict[str, Any]

    def as_db_params(self) -> tuple[object, ...]:
        prov = json.dumps(self.input_provenance, separators=(",", ":"), sort_keys=True)
        return (
            self.feature_schema_version,
            self.feature_schema_hash,
            self.canonical_instrument_id,
            self.market_family,
            self.product_type,
            self.margin_account_mode,
            self.instrument_metadata_snapshot_id,
            self.symbol,
            self.timeframe,
            self.start_ts_ms,
            self.atr_14,
            self.atrp_14,
            self.rsi_14,
            self.ret_1,
            self.ret_5,
            self.momentum_score,
            self.impulse_body_ratio,
            self.impulse_upper_wick_ratio,
            self.impulse_lower_wick_ratio,
            self.range_score,
            self.trend_ema_fast,
            self.trend_ema_slow,
            self.trend_slope_proxy,
            self.trend_dir,
            self.confluence_score_0_100,
            self.vol_z_50,
            self.spread_bps,
            self.bid_depth_usdt_top25,
            self.ask_depth_usdt_top25,
            self.orderbook_imbalance,
            self.depth_balance_ratio,
            self.depth_to_bar_volume_ratio,
            self.impact_buy_bps_5000,
            self.impact_sell_bps_5000,
            self.impact_buy_bps_10000,
            self.impact_sell_bps_10000,
            self.execution_cost_bps,
            self.volatility_cost_bps,
            self.funding_rate,
            self.funding_rate_bps,
            self.funding_cost_bps_window,
            self.funding_time_to_next_ms,
            self.open_interest,
            self.open_interest_change_pct,
            self.mark_index_spread_bps,
            self.basis_bps,
            self.session_drift_bps,
            self.spread_persistence_bps,
            self.mean_reversion_pressure_0_100,
            self.breakout_compression_score_0_100,
            self.realized_vol_cluster_0_100,
            self.liquidation_distance_bps_max_leverage,
            self.data_completeness_0_1,
            self.staleness_score_0_1,
            self.gap_count_lookback,
            self.event_distance_ms,
            self.feature_quality_status,
            self.orderbook_age_ms,
            self.funding_age_ms,
            self.open_interest_age_ms,
            self.liquidity_source,
            self.funding_source,
            self.open_interest_source,
            self.source_event_id,
            self.computed_ts_ms,
            prov,
        )


UPSERT_FEATURE_SQL = """
INSERT INTO features.candle_features (
    feature_schema_version,
    feature_schema_hash,
    canonical_instrument_id,
    market_family,
    product_type,
    margin_account_mode,
    instrument_metadata_snapshot_id,
    symbol,
    timeframe,
    start_ts_ms,
    atr_14,
    atrp_14,
    rsi_14,
    ret_1,
    ret_5,
    momentum_score,
    impulse_body_ratio,
    impulse_upper_wick_ratio,
    impulse_lower_wick_ratio,
    range_score,
    trend_ema_fast,
    trend_ema_slow,
    trend_slope_proxy,
    trend_dir,
    confluence_score_0_100,
    vol_z_50,
    spread_bps,
    bid_depth_usdt_top25,
    ask_depth_usdt_top25,
    orderbook_imbalance,
    depth_balance_ratio,
    depth_to_bar_volume_ratio,
    impact_buy_bps_5000,
    impact_sell_bps_5000,
    impact_buy_bps_10000,
    impact_sell_bps_10000,
    execution_cost_bps,
    volatility_cost_bps,
    funding_rate,
    funding_rate_bps,
    funding_cost_bps_window,
    funding_time_to_next_ms,
    open_interest,
    open_interest_change_pct,
    mark_index_spread_bps,
    basis_bps,
    session_drift_bps,
    spread_persistence_bps,
    mean_reversion_pressure_0_100,
    breakout_compression_score_0_100,
    realized_vol_cluster_0_100,
    liquidation_distance_bps_max_leverage,
    data_completeness_0_1,
    staleness_score_0_1,
    gap_count_lookback,
    event_distance_ms,
    feature_quality_status,
    orderbook_age_ms,
    funding_age_ms,
    open_interest_age_ms,
    liquidity_source,
    funding_source,
    open_interest_source,
    source_event_id,
    computed_ts_ms,
    input_provenance_json
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
)
ON CONFLICT (canonical_instrument_id, timeframe, start_ts_ms) DO UPDATE SET
    feature_schema_version = EXCLUDED.feature_schema_version,
    feature_schema_hash = EXCLUDED.feature_schema_hash,
    canonical_instrument_id = EXCLUDED.canonical_instrument_id,
    market_family = EXCLUDED.market_family,
    product_type = EXCLUDED.product_type,
    margin_account_mode = EXCLUDED.margin_account_mode,
    instrument_metadata_snapshot_id = EXCLUDED.instrument_metadata_snapshot_id,
    atr_14 = EXCLUDED.atr_14,
    atrp_14 = EXCLUDED.atrp_14,
    rsi_14 = EXCLUDED.rsi_14,
    ret_1 = EXCLUDED.ret_1,
    ret_5 = EXCLUDED.ret_5,
    momentum_score = EXCLUDED.momentum_score,
    impulse_body_ratio = EXCLUDED.impulse_body_ratio,
    impulse_upper_wick_ratio = EXCLUDED.impulse_upper_wick_ratio,
    impulse_lower_wick_ratio = EXCLUDED.impulse_lower_wick_ratio,
    range_score = EXCLUDED.range_score,
    trend_ema_fast = EXCLUDED.trend_ema_fast,
    trend_ema_slow = EXCLUDED.trend_ema_slow,
    trend_slope_proxy = EXCLUDED.trend_slope_proxy,
    trend_dir = EXCLUDED.trend_dir,
    confluence_score_0_100 = EXCLUDED.confluence_score_0_100,
    vol_z_50 = EXCLUDED.vol_z_50,
    spread_bps = EXCLUDED.spread_bps,
    bid_depth_usdt_top25 = EXCLUDED.bid_depth_usdt_top25,
    ask_depth_usdt_top25 = EXCLUDED.ask_depth_usdt_top25,
    orderbook_imbalance = EXCLUDED.orderbook_imbalance,
    depth_balance_ratio = EXCLUDED.depth_balance_ratio,
    depth_to_bar_volume_ratio = EXCLUDED.depth_to_bar_volume_ratio,
    impact_buy_bps_5000 = EXCLUDED.impact_buy_bps_5000,
    impact_sell_bps_5000 = EXCLUDED.impact_sell_bps_5000,
    impact_buy_bps_10000 = EXCLUDED.impact_buy_bps_10000,
    impact_sell_bps_10000 = EXCLUDED.impact_sell_bps_10000,
    execution_cost_bps = EXCLUDED.execution_cost_bps,
    volatility_cost_bps = EXCLUDED.volatility_cost_bps,
    funding_rate = EXCLUDED.funding_rate,
    funding_rate_bps = EXCLUDED.funding_rate_bps,
    funding_cost_bps_window = EXCLUDED.funding_cost_bps_window,
    funding_time_to_next_ms = EXCLUDED.funding_time_to_next_ms,
    open_interest = EXCLUDED.open_interest,
    open_interest_change_pct = EXCLUDED.open_interest_change_pct,
    mark_index_spread_bps = EXCLUDED.mark_index_spread_bps,
    basis_bps = EXCLUDED.basis_bps,
    session_drift_bps = EXCLUDED.session_drift_bps,
    spread_persistence_bps = EXCLUDED.spread_persistence_bps,
    mean_reversion_pressure_0_100 = EXCLUDED.mean_reversion_pressure_0_100,
    breakout_compression_score_0_100 = EXCLUDED.breakout_compression_score_0_100,
    realized_vol_cluster_0_100 = EXCLUDED.realized_vol_cluster_0_100,
    liquidation_distance_bps_max_leverage = EXCLUDED.liquidation_distance_bps_max_leverage,
    data_completeness_0_1 = EXCLUDED.data_completeness_0_1,
    staleness_score_0_1 = EXCLUDED.staleness_score_0_1,
    gap_count_lookback = EXCLUDED.gap_count_lookback,
    event_distance_ms = EXCLUDED.event_distance_ms,
    feature_quality_status = EXCLUDED.feature_quality_status,
    orderbook_age_ms = EXCLUDED.orderbook_age_ms,
    funding_age_ms = EXCLUDED.funding_age_ms,
    open_interest_age_ms = EXCLUDED.open_interest_age_ms,
    liquidity_source = EXCLUDED.liquidity_source,
    funding_source = EXCLUDED.funding_source,
    open_interest_source = EXCLUDED.open_interest_source,
    source_event_id = EXCLUDED.source_event_id,
    computed_ts_ms = EXCLUDED.computed_ts_ms,
    input_provenance_json = EXCLUDED.input_provenance_json
"""


class FeatureRepository:
    def __init__(self, database_url: str, *, logger: logging.Logger | None = None) -> None:
        self._database_url = database_url
        self._logger = logger or logging.getLogger("feature_engine.repo")

    def ping(self) -> bool:
        with self._connect() as conn:
            conn.execute("select 1")
        return True

    def fetch_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_start_ts_ms: int,
        limit: int,
    ) -> list[StoredCandle]:
        sql = """
        SELECT
            symbol,
            timeframe,
            start_ts_ms,
            open AS o,
            high AS h,
            low AS l,
            close AS c,
            base_vol,
            quote_vol,
            usdt_vol
        FROM tsdb.candles
        WHERE symbol = %s
          AND timeframe = %s
          AND start_ts_ms <= %s
        ORDER BY start_ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, end_start_ts_ms, limit)).fetchall()
        rows.reverse()
        return [self._stored_candle_from_row(row) for row in rows]

    def upsert_feature(self, row: CandleFeatureRow) -> None:
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(UPSERT_FEATURE_SQL, row.as_db_params())

    def get_latest_feature(
        self,
        *,
        symbol: str,
        timeframe: str,
        canonical_instrument_id: str | None = None,
        market_family: str | None = None,
    ) -> dict[str, Any] | None:
        return self._get_feature_row(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=None,
            canonical_instrument_id=canonical_instrument_id,
            market_family=market_family,
        )

    def _get_feature_row(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int | None,
        canonical_instrument_id: str | None,
        market_family: str | None,
    ) -> dict[str, Any] | None:
        filters = ["symbol = %s", "timeframe = %s"]
        params: list[object] = [symbol, timeframe]
        if canonical_instrument_id:
            filters.append("canonical_instrument_id = %s")
            params.append(canonical_instrument_id)
        if market_family:
            filters.append("market_family = %s")
            params.append(market_family)
        if start_ts_ms is not None:
            filters.append("start_ts_ms = %s")
            params.append(start_ts_ms)
            order_limit = "LIMIT 1"
        else:
            order_limit = "ORDER BY start_ts_ms DESC LIMIT 1"
        sql = f"""
        SELECT *
        FROM features.candle_features
        WHERE {" AND ".join(filters)}
        {order_limit}
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, params).fetchone()
        return self._json_ready_row(row)

    def fetch_orderbook_snapshot(
        self,
        *,
        symbol: str,
        max_ts_ms: int,
    ) -> OrderBookSnapshot | None:
        sql = """
        WITH latest AS (
            SELECT ts_ms
            FROM tsdb.orderbook_levels
            WHERE symbol = %s
              AND ts_ms <= %s
            ORDER BY ts_ms DESC
            LIMIT 1
        )
        SELECT symbol, ts_ms, side, level, price, size
        FROM tsdb.orderbook_levels
        WHERE symbol = %s
          AND ts_ms = (SELECT ts_ms FROM latest)
        ORDER BY side, level
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, max_ts_ms, symbol)).fetchall()
        if not rows:
            return None
        bids: list[tuple[float, float]] = []
        asks: list[tuple[float, float]] = []
        for row in rows:
            side = str(row["side"])
            level = (float(row["price"]), float(row["size"]))
            if side == "bid":
                bids.append(level)
            elif side == "ask":
                asks.append(level)
        first = rows[0]
        return OrderBookSnapshot(
            symbol=str(first["symbol"]),
            ts_ms=int(first["ts_ms"]),
            bids=bids,
            asks=asks,
        )

    def fetch_ticker_snapshot(
        self,
        *,
        symbol: str,
        max_ts_ms: int,
    ) -> TickerSnapshot | None:
        sql = """
        SELECT symbol, ts_ms, source, bid_pr, ask_pr, bid_sz, ask_sz, last_pr, mark_price, index_price
        FROM tsdb.ticker
        WHERE symbol = %s
          AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, max_ts_ms)).fetchone()
        if row is None:
            return None
        return TickerSnapshot(
            symbol=str(row["symbol"]),
            ts_ms=int(row["ts_ms"]),
            source=str(row.get("source") or "ticker"),
            bid_pr=_to_optional_float(row.get("bid_pr")),
            ask_pr=_to_optional_float(row.get("ask_pr")),
            bid_sz=_to_optional_float(row.get("bid_sz")),
            ask_sz=_to_optional_float(row.get("ask_sz")),
            last_pr=_to_optional_float(row.get("last_pr")),
            mark_price=_to_optional_float(row.get("mark_price")),
            index_price=_to_optional_float(row.get("index_price")),
        )

    def fetch_recent_ticker_snapshots(
        self,
        *,
        symbol: str,
        max_ts_ms: int,
        limit: int,
    ) -> list[TickerSnapshot]:
        sql = """
        SELECT symbol, ts_ms, source, bid_pr, ask_pr, bid_sz, ask_sz, last_pr, mark_price, index_price
        FROM tsdb.ticker
        WHERE symbol = %s
          AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, max_ts_ms, limit)).fetchall()
        return [
            TickerSnapshot(
                symbol=str(row["symbol"]),
                ts_ms=int(row["ts_ms"]),
                source=str(row.get("source") or "ticker"),
                bid_pr=_to_optional_float(row.get("bid_pr")),
                ask_pr=_to_optional_float(row.get("ask_pr")),
                bid_sz=_to_optional_float(row.get("bid_sz")),
                ask_sz=_to_optional_float(row.get("ask_sz")),
                last_pr=_to_optional_float(row.get("last_pr")),
                mark_price=_to_optional_float(row.get("mark_price")),
                index_price=_to_optional_float(row.get("index_price")),
            )
            for row in rows
        ]

    def fetch_funding_snapshot(
        self,
        *,
        symbol: str,
        max_ts_ms: int,
    ) -> FundingSnapshot | None:
        sql = """
        SELECT symbol, ts_ms, source, funding_rate, interval_hours, next_update_ms
        FROM tsdb.funding_rate
        WHERE symbol = %s
          AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, max_ts_ms)).fetchone()
        if row is None:
            return None
        funding_rate = _to_optional_float(row.get("funding_rate"))
        if funding_rate is None:
            return None
        interval_hours = row.get("interval_hours")
        next_update_ms = row.get("next_update_ms")
        return FundingSnapshot(
            symbol=str(row["symbol"]),
            ts_ms=int(row["ts_ms"]),
            source=str(row.get("source") or "funding_rate"),
            funding_rate=funding_rate,
            interval_hours=int(interval_hours) if interval_hours is not None else None,
            next_update_ms=int(next_update_ms) if next_update_ms is not None else None,
        )

    def fetch_open_interest_snapshot(
        self,
        *,
        symbol: str,
        max_ts_ms: int,
    ) -> OpenInterestSnapshot | None:
        sql = """
        SELECT symbol, ts_ms, source, size
        FROM tsdb.open_interest
        WHERE symbol = %s
          AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, max_ts_ms)).fetchone()
        if row is None:
            return None
        size = _to_optional_float(row.get("size"))
        if size is None:
            return None
        return OpenInterestSnapshot(
            symbol=str(row["symbol"]),
            ts_ms=int(row["ts_ms"]),
            source=str(row.get("source") or "open_interest"),
            size=size,
        )

    def get_feature_at(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        canonical_instrument_id: str | None = None,
        market_family: str | None = None,
    ) -> dict[str, Any] | None:
        return self._get_feature_row(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            canonical_instrument_id=canonical_instrument_id,
            market_family=market_family,
        )

    def get_latest_trend_dirs(
        self,
        *,
        symbol: str,
        timeframes: Sequence[str],
        canonical_instrument_id: str | None = None,
    ) -> dict[str, int]:
        filters = ["symbol = %s", "timeframe = ANY(%s)"]
        params: list[object] = [symbol, list(timeframes)]
        if canonical_instrument_id:
            filters.append("canonical_instrument_id = %s")
            params.append(canonical_instrument_id)
        sql = f"""
        SELECT timeframe, trend_dir
        FROM (
            SELECT
                timeframe,
                trend_dir,
                ROW_NUMBER() OVER (PARTITION BY timeframe ORDER BY start_ts_ms DESC) AS rn
            FROM features.candle_features
            WHERE {" AND ".join(filters)}
        ) latest
        WHERE rn = 1
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, params).fetchall()
        return {str(row["timeframe"]): int(row["trend_dir"]) for row in rows}

    def _connect(
        self,
        *,
        row_factory: Any | None = None,
    ) -> psycopg.Connection[Any]:
        kwargs: dict[str, Any] = {
            "connect_timeout": 5,
            "autocommit": True,
        }
        if row_factory is not None:
            kwargs["row_factory"] = row_factory
        return psycopg.connect(self._database_url, **kwargs)

    def _stored_candle_from_row(self, row: dict[str, Any]) -> StoredCandle:
        return StoredCandle(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            start_ts_ms=int(row["start_ts_ms"]),
            o=float(row["o"]),
            h=float(row["h"]),
            l=float(row["l"]),
            c=float(row["c"]),
            base_vol=float(row["base_vol"]),
            quote_vol=float(row["quote_vol"]),
            usdt_vol=float(row["usdt_vol"]),
        )

    def _json_ready_row(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)


def _to_optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
