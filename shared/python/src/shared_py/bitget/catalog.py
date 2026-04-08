from __future__ import annotations

import json
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
from redis import Redis

from shared_py.bitget.config import BitgetSettings
from shared_py.bitget.discovery import BitgetMarketDiscoveryClient
from shared_py.bitget.instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentCatalogSnapshot,
    BitgetMarketCapabilityMatrixRow,
)

_CACHE_KEY = "bitget:instrument_catalog:current:v1"


class UnknownInstrumentError(LookupError):
    pass


class InstrumentCatalogUnavailableError(RuntimeError):
    pass


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


class BitgetInstrumentCatalog:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        database_url: str,
        redis_url: str,
        source_service: str,
        cache_ttl_sec: int = 900,
        max_stale_sec: int = 1800,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._database_url = database_url
        self._redis_url = redis_url
        self._source_service = source_service
        self._cache_ttl_sec = cache_ttl_sec
        self._max_stale_sec = max_stale_sec
        self._discovery = BitgetMarketDiscoveryClient(bitget_settings)
        self._memory_snapshot: BitgetInstrumentCatalogSnapshot | None = None

    def schema_ready(self) -> tuple[bool, str]:
        query = """
        SELECT
            to_regclass('app.instrument_catalog_snapshots') IS NOT NULL AS snapshots_ready,
            to_regclass('app.instrument_catalog_entries') IS NOT NULL AS entries_ready
        """
        try:
            with self._connect() as conn:
                row = conn.execute(query).fetchone()
        except Exception as exc:
            return False, str(exc)[:200]
        if row is None:
            return False, "catalog_schema_query_failed"
        if not row["snapshots_ready"] or not row["entries_ready"]:
            return False, "missing_catalog_tables"
        return True, "ok"

    def refresh_catalog(
        self,
        *,
        refresh_reason: str,
    ) -> BitgetInstrumentCatalogSnapshot:
        snapshot = self._discovery.discover_catalog_snapshot(
            source_service=self._source_service,
            refresh_reason=refresh_reason,
            candidate_margin_symbols=self._bitget_settings.discovery_symbols,
        )
        self._persist_snapshot(snapshot)
        self._cache_snapshot(snapshot)
        self._memory_snapshot = snapshot
        return snapshot

    def get_snapshot(
        self,
        *,
        refresh_if_missing: bool = False,
        refresh_reason: str = "lookup",
    ) -> BitgetInstrumentCatalogSnapshot | None:
        if self._memory_snapshot is not None and not self._is_snapshot_stale(self._memory_snapshot):
            return self._memory_snapshot
        cached = self._load_cached_snapshot()
        if cached is not None and not self._is_snapshot_stale(cached):
            self._memory_snapshot = cached
            return cached
        db_snapshot = self._load_db_snapshot()
        if db_snapshot is not None and not self._is_snapshot_stale(db_snapshot):
            self._memory_snapshot = db_snapshot
            self._cache_snapshot(db_snapshot)
            return db_snapshot
        if refresh_if_missing:
            return self.refresh_catalog(refresh_reason=refresh_reason)
        return db_snapshot or cached or self._memory_snapshot

    def require_catalog(self, *, refresh_if_missing: bool = False) -> BitgetInstrumentCatalogSnapshot:
        snapshot = self.get_snapshot(
            refresh_if_missing=refresh_if_missing,
            refresh_reason="require_catalog",
        )
        if snapshot is None:
            raise InstrumentCatalogUnavailableError("instrument_catalog_unavailable")
        return snapshot

    def resolve(
        self,
        *,
        symbol: str,
        market_family: str | None = None,
        product_type: str | None = None,
        margin_account_mode: str | None = None,
        refresh_if_missing: bool = False,
    ) -> BitgetInstrumentCatalogEntry:
        snapshot = self.require_catalog(refresh_if_missing=refresh_if_missing)
        normalized_symbol = str(symbol).strip().upper()
        family = str(market_family or self._bitget_settings.market_family).strip().lower()
        product = str(product_type or self._bitget_settings.product_type).strip().upper() or None
        margin_mode = str(
            margin_account_mode or self._bitget_settings.margin_account_mode
        ).strip().lower() or None
        candidates = [
            entry
            for entry in snapshot.entries
            if normalized_symbol in entry.symbol_aliases and entry.market_family == family
        ]
        if product is not None:
            narrowed = [entry for entry in candidates if entry.product_type == product]
            if narrowed:
                candidates = narrowed
        if margin_mode is not None:
            narrowed = [
                entry for entry in candidates if entry.margin_account_mode == margin_mode
            ]
            if narrowed:
                candidates = narrowed
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            exact = [entry for entry in candidates if entry.symbol == normalized_symbol]
            if len(exact) == 1:
                return exact[0]
        raise UnknownInstrumentError(
            f"instrument_not_found symbol={normalized_symbol} family={family} product={product} margin_mode={margin_mode}"
        )

    def resolve_for_trading(
        self,
        *,
        symbol: str,
        market_family: str | None = None,
        product_type: str | None = None,
        margin_account_mode: str | None = None,
        refresh_if_missing: bool = False,
    ) -> BitgetInstrumentCatalogEntry:
        entry = self.resolve(
            symbol=symbol,
            market_family=market_family,
            product_type=product_type,
            margin_account_mode=margin_account_mode,
            refresh_if_missing=refresh_if_missing,
        )
        if not entry.trading_enabled:
            raise UnknownInstrumentError(
                f"instrument_not_tradeable canonical_id={entry.canonical_instrument_id} status={entry.trading_status}"
            )
        return entry

    def resolve_for_subscription(
        self,
        *,
        symbol: str,
        market_family: str | None = None,
        product_type: str | None = None,
        margin_account_mode: str | None = None,
        refresh_if_missing: bool = False,
    ) -> BitgetInstrumentCatalogEntry:
        entry = self.resolve(
            symbol=symbol,
            market_family=market_family,
            product_type=product_type,
            margin_account_mode=margin_account_mode,
            refresh_if_missing=refresh_if_missing,
        )
        if not entry.subscribe_enabled:
            raise UnknownInstrumentError(
                f"instrument_not_subscribable canonical_id={entry.canonical_instrument_id} status={entry.trading_status}"
            )
        return entry

    def health_payload(self) -> dict[str, Any]:
        schema_ok, schema_detail = self.schema_ready()
        snapshot = self.get_snapshot(refresh_if_missing=False)
        if snapshot is None:
            return {
                "schema_ready": schema_ok,
                "schema_detail": schema_detail,
                "catalog_loaded": False,
                "status": "missing",
            }
        completed = snapshot.fetch_completed_ts_ms or snapshot.fetch_started_ts_ms
        age_sec = max(0.0, (time.time() * 1000 - completed) / 1000.0)
        return {
            "schema_ready": schema_ok,
            "schema_detail": schema_detail,
            "catalog_loaded": True,
            "status": snapshot.status,
            "snapshot_id": snapshot.snapshot_id,
            "source_service": snapshot.source_service,
            "refresh_reason": snapshot.refresh_reason,
            "age_sec": round(age_sec, 3),
            "stale": self._is_snapshot_stale(snapshot),
            "refreshed_families": list(snapshot.refreshed_families),
            "counts_by_family": dict(snapshot.counts_by_family),
            "category_count": len(snapshot.capability_matrix),
            "warnings": list(snapshot.warnings),
            "errors": list(snapshot.errors),
        }

    def current_configured_instrument(
        self,
        *,
        refresh_if_missing: bool = False,
        require_subscription: bool = False,
    ) -> BitgetInstrumentCatalogEntry:
        resolver = self.resolve_for_subscription if require_subscription else self.resolve
        return resolver(
            symbol=self._bitget_settings.symbol,
            market_family=self._bitget_settings.market_family,
            product_type=(
                self._bitget_settings.product_type
                if self._bitget_settings.market_family == "futures"
                else None
            ),
            margin_account_mode=(
                self._bitget_settings.margin_account_mode
                if self._bitget_settings.market_family == "margin"
                else None
            ),
            refresh_if_missing=refresh_if_missing,
        )

    def _persist_snapshot(self, snapshot: BitgetInstrumentCatalogSnapshot) -> None:
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO app.instrument_catalog_snapshots (
                        snapshot_id,
                        source_service,
                        refresh_reason,
                        status,
                        fetch_started_ts_ms,
                        fetch_completed_ts_ms,
                        refreshed_families_json,
                        counts_json,
                        capability_matrix_json,
                        warnings_json,
                        errors_json
                    ) VALUES (
                        %(snapshot_id)s,
                        %(source_service)s,
                        %(refresh_reason)s,
                        %(status)s,
                        %(fetch_started_ts_ms)s,
                        %(fetch_completed_ts_ms)s,
                        %(refreshed_families_json)s,
                        %(counts_json)s,
                        %(capability_matrix_json)s,
                        %(warnings_json)s,
                        %(errors_json)s
                    )
                    """,
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "source_service": snapshot.source_service,
                        "refresh_reason": snapshot.refresh_reason,
                        "status": snapshot.status,
                        "fetch_started_ts_ms": snapshot.fetch_started_ts_ms,
                        "fetch_completed_ts_ms": snapshot.fetch_completed_ts_ms,
                        "refreshed_families_json": Json(snapshot.refreshed_families),
                        "counts_json": Json(snapshot.counts_by_family),
                        "capability_matrix_json": Json(
                            [row.model_dump(mode="json") for row in snapshot.capability_matrix]
                        ),
                        "warnings_json": Json(snapshot.warnings),
                        "errors_json": Json(snapshot.errors),
                    },
                )
                for entry in snapshot.entries:
                    conn.execute(
                        """
                        INSERT INTO app.instrument_catalog_entries (
                            canonical_instrument_id,
                            snapshot_id,
                            venue,
                            market_family,
                            symbol,
                            symbol_aliases_json,
                            category_key,
                            product_type,
                            margin_account_mode,
                            margin_coin,
                            base_coin,
                            quote_coin,
                            settle_coin,
                            public_ws_inst_type,
                            private_ws_inst_type,
                            metadata_source,
                            metadata_verified,
                            status,
                            inventory_visible,
                            analytics_eligible,
                            paper_shadow_eligible,
                            live_execution_enabled,
                            execution_disabled,
                            supports_funding,
                            supports_open_interest,
                            supports_long_short,
                            supports_shorting,
                            supports_reduce_only,
                            supports_leverage,
                            uses_spot_public_market_data,
                            price_tick_size,
                            quantity_step,
                            quantity_min,
                            quantity_max,
                            market_order_quantity_max,
                            min_notional_quote,
                            price_precision,
                            quantity_precision,
                            quote_precision,
                            leverage_min,
                            leverage_max,
                            funding_interval_hours,
                            symbol_type,
                            supported_margin_coins_json,
                            trading_status,
                            trading_enabled,
                            subscribe_enabled,
                            session_metadata_json,
                            refresh_ts_ms,
                            raw_metadata_json
                        ) VALUES (
                            %(canonical_instrument_id)s,
                            %(snapshot_id)s,
                            %(venue)s,
                            %(market_family)s,
                            %(symbol)s,
                            %(symbol_aliases_json)s,
                            %(category_key)s,
                            %(product_type)s,
                            %(margin_account_mode)s,
                            %(margin_coin)s,
                            %(base_coin)s,
                            %(quote_coin)s,
                            %(settle_coin)s,
                            %(public_ws_inst_type)s,
                            %(private_ws_inst_type)s,
                            %(metadata_source)s,
                            %(metadata_verified)s,
                            %(status)s,
                            %(inventory_visible)s,
                            %(analytics_eligible)s,
                            %(paper_shadow_eligible)s,
                            %(live_execution_enabled)s,
                            %(execution_disabled)s,
                            %(supports_funding)s,
                            %(supports_open_interest)s,
                            %(supports_long_short)s,
                            %(supports_shorting)s,
                            %(supports_reduce_only)s,
                            %(supports_leverage)s,
                            %(uses_spot_public_market_data)s,
                            %(price_tick_size)s,
                            %(quantity_step)s,
                            %(quantity_min)s,
                            %(quantity_max)s,
                            %(market_order_quantity_max)s,
                            %(min_notional_quote)s,
                            %(price_precision)s,
                            %(quantity_precision)s,
                            %(quote_precision)s,
                            %(leverage_min)s,
                            %(leverage_max)s,
                            %(funding_interval_hours)s,
                            %(symbol_type)s,
                            %(supported_margin_coins_json)s,
                            %(trading_status)s,
                            %(trading_enabled)s,
                            %(subscribe_enabled)s,
                            %(session_metadata_json)s,
                            %(refresh_ts_ms)s,
                            %(raw_metadata_json)s
                        )
                        ON CONFLICT (canonical_instrument_id) DO UPDATE SET
                            snapshot_id = EXCLUDED.snapshot_id,
                            venue = EXCLUDED.venue,
                            market_family = EXCLUDED.market_family,
                            symbol = EXCLUDED.symbol,
                            symbol_aliases_json = EXCLUDED.symbol_aliases_json,
                            category_key = EXCLUDED.category_key,
                            product_type = EXCLUDED.product_type,
                            margin_account_mode = EXCLUDED.margin_account_mode,
                            margin_coin = EXCLUDED.margin_coin,
                            base_coin = EXCLUDED.base_coin,
                            quote_coin = EXCLUDED.quote_coin,
                            settle_coin = EXCLUDED.settle_coin,
                            public_ws_inst_type = EXCLUDED.public_ws_inst_type,
                            private_ws_inst_type = EXCLUDED.private_ws_inst_type,
                            metadata_source = EXCLUDED.metadata_source,
                            metadata_verified = EXCLUDED.metadata_verified,
                            status = EXCLUDED.status,
                            inventory_visible = EXCLUDED.inventory_visible,
                            analytics_eligible = EXCLUDED.analytics_eligible,
                            paper_shadow_eligible = EXCLUDED.paper_shadow_eligible,
                            live_execution_enabled = EXCLUDED.live_execution_enabled,
                            execution_disabled = EXCLUDED.execution_disabled,
                            supports_funding = EXCLUDED.supports_funding,
                            supports_open_interest = EXCLUDED.supports_open_interest,
                            supports_long_short = EXCLUDED.supports_long_short,
                            supports_shorting = EXCLUDED.supports_shorting,
                            supports_reduce_only = EXCLUDED.supports_reduce_only,
                            supports_leverage = EXCLUDED.supports_leverage,
                            uses_spot_public_market_data = EXCLUDED.uses_spot_public_market_data,
                            price_tick_size = EXCLUDED.price_tick_size,
                            quantity_step = EXCLUDED.quantity_step,
                            quantity_min = EXCLUDED.quantity_min,
                            quantity_max = EXCLUDED.quantity_max,
                            market_order_quantity_max = EXCLUDED.market_order_quantity_max,
                            min_notional_quote = EXCLUDED.min_notional_quote,
                            price_precision = EXCLUDED.price_precision,
                            quantity_precision = EXCLUDED.quantity_precision,
                            quote_precision = EXCLUDED.quote_precision,
                            leverage_min = EXCLUDED.leverage_min,
                            leverage_max = EXCLUDED.leverage_max,
                            funding_interval_hours = EXCLUDED.funding_interval_hours,
                            symbol_type = EXCLUDED.symbol_type,
                            supported_margin_coins_json = EXCLUDED.supported_margin_coins_json,
                            trading_status = EXCLUDED.trading_status,
                            trading_enabled = EXCLUDED.trading_enabled,
                            subscribe_enabled = EXCLUDED.subscribe_enabled,
                            session_metadata_json = EXCLUDED.session_metadata_json,
                            refresh_ts_ms = EXCLUDED.refresh_ts_ms,
                            raw_metadata_json = EXCLUDED.raw_metadata_json,
                            updated_ts = now()
                        """,
                        {
                            **entry.model_dump(mode="json"),
                            "snapshot_id": snapshot.snapshot_id,
                            "symbol_aliases_json": Json(entry.symbol_aliases),
                            "supported_margin_coins_json": Json(entry.supported_margin_coins),
                            "session_metadata_json": Json(_json_safe(entry.session_metadata)),
                            "raw_metadata_json": Json(_json_safe(entry.raw_metadata)),
                        },
                    )
                if snapshot.refreshed_families:
                    refreshed_ids = [entry.canonical_instrument_id for entry in snapshot.entries]
                    conn.execute(
                        """
                        UPDATE app.instrument_catalog_entries
                        SET
                            snapshot_id = %(snapshot_id)s,
                            trading_status = 'missing_from_latest_snapshot',
                            inventory_visible = false,
                            analytics_eligible = false,
                            paper_shadow_eligible = false,
                            live_execution_enabled = false,
                            execution_disabled = false,
                            trading_enabled = false,
                            subscribe_enabled = false,
                            updated_ts = now()
                        WHERE market_family = ANY(%(refreshed_families)s)
                          AND canonical_instrument_id <> ALL(%(refreshed_ids)s)
                        """,
                        {
                            "snapshot_id": snapshot.snapshot_id,
                            "refreshed_families": snapshot.refreshed_families,
                            "refreshed_ids": refreshed_ids or [""],
                        },
                    )

    def _load_cached_snapshot(self) -> BitgetInstrumentCatalogSnapshot | None:
        try:
            cache = self._redis()
            raw = cache.get(_CACHE_KEY)
        except Exception:
            return None
        if not raw:
            return None
        try:
            return BitgetInstrumentCatalogSnapshot.model_validate_json(raw)
        except Exception:
            return None

    def _cache_snapshot(self, snapshot: BitgetInstrumentCatalogSnapshot) -> None:
        try:
            cache = self._redis()
            cache.setex(_CACHE_KEY, self._cache_ttl_sec, snapshot.model_dump_json())
        except Exception:
            return

    def _load_db_snapshot(self) -> BitgetInstrumentCatalogSnapshot | None:
        try:
            with self._connect() as conn:
                meta = conn.execute(
                    """
                    SELECT *
                    FROM app.instrument_catalog_snapshots
                    ORDER BY fetch_completed_ts_ms DESC NULLS LAST, fetch_started_ts_ms DESC
                    LIMIT 1
                    """
                ).fetchone()
                if meta is None:
                    return None
                rows = conn.execute(
                    """
                    SELECT *
                    FROM app.instrument_catalog_entries
                    ORDER BY market_family, symbol, product_type NULLS LAST
                    """
                ).fetchall()
        except Exception:
            return None
        entries = [
            BitgetInstrumentCatalogEntry.model_validate(
                {
                    **dict(row),
                    "symbol_aliases": list(row["symbol_aliases_json"] or []),
                    "supported_margin_coins": list(row.get("supported_margin_coins_json") or []),
                    "session_metadata": dict(row["session_metadata_json"] or {}),
                    "raw_metadata": dict(row["raw_metadata_json"] or {}),
                }
            )
            for row in rows
        ]
        meta_dict = dict(meta)
        return BitgetInstrumentCatalogSnapshot(
            snapshot_id=str(meta_dict["snapshot_id"]),
            source_service=str(meta_dict["source_service"]),
            refresh_reason=str(meta_dict["refresh_reason"]),
            status=str(meta_dict["status"]),
            fetch_started_ts_ms=int(meta_dict["fetch_started_ts_ms"]),
            fetch_completed_ts_ms=int(meta_dict["fetch_completed_ts_ms"])
            if meta_dict.get("fetch_completed_ts_ms") is not None
            else None,
            refreshed_families=list(meta_dict.get("refreshed_families_json") or []),
            counts_by_family=dict(meta_dict.get("counts_json") or {}),
            capability_matrix=[
                BitgetMarketCapabilityMatrixRow.model_validate(item)
                for item in list(meta_dict.get("capability_matrix_json") or [])
                if isinstance(item, dict)
            ],
            warnings=list(meta_dict.get("warnings_json") or []),
            errors=list(meta_dict.get("errors_json") or []),
            entries=entries,
        )

    def _is_snapshot_stale(self, snapshot: BitgetInstrumentCatalogSnapshot) -> bool:
        completed = snapshot.fetch_completed_ts_ms or snapshot.fetch_started_ts_ms
        return (time.time() * 1000 - completed) > self._max_stale_sec * 1000

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self._database_url, row_factory=dict_row, connect_timeout=5)

    def _redis(self) -> Redis:
        return Redis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
