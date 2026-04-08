from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import httpx

from shared_py.bitget.config import BitgetSettings, ProductType
from shared_py.bitget.http import build_private_rest_headers, build_query_string
from shared_py.bitget.instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentCatalogSnapshot,
    BitgetInstrumentIdentity,
    BitgetMarketCapabilityMatrixRow,
    MarginAccountMode,
    build_capability_matrix,
    endpoint_profile_for,
    trading_status_allows_subscription,
    trading_status_allows_trading,
)

_FUTURES_PRODUCT_TYPES: tuple[ProductType, ...] = (
    "USDT-FUTURES",
    "USDC-FUTURES",
    "COIN-FUTURES",
)


class BitgetMarketDiscoveryClient:
    def __init__(
        self,
        settings: BitgetSettings,
        *,
        timeout_sec: float = 10.0,
    ) -> None:
        self._settings = settings
        self._timeout_sec = timeout_sec

    def discover_supported_market_universe(
        self,
        *,
        candidate_margin_symbols: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        snapshot = self.discover_catalog_snapshot(
            source_service="bitget.discovery",
            refresh_reason="discover_supported_market_universe",
            candidate_margin_symbols=candidate_margin_symbols,
        )
        spot = [entry.identity() for entry in snapshot.entries if entry.market_family == "spot"]
        futures = [
            entry.identity() for entry in snapshot.entries if entry.market_family == "futures"
        ]
        margin = [
            entry.identity() for entry in snapshot.entries if entry.market_family == "margin"
        ]
        return {
            "schema_version": snapshot.schema_version,
            "snapshot_id": snapshot.snapshot_id,
            "status": snapshot.status,
            "categories": [item.model_dump(mode="json") for item in snapshot.capability_matrix],
            "spot": [item.model_dump(mode="json") for item in spot],
            "margin": [item.model_dump(mode="json") for item in margin],
            "futures": [item.model_dump(mode="json") for item in futures],
        }

    def discover_catalog_snapshot(
        self,
        *,
        source_service: str,
        refresh_reason: str,
        candidate_margin_symbols: Sequence[str] | None = None,
    ) -> BitgetInstrumentCatalogSnapshot:
        started = int(time.time() * 1000)
        entries: list[BitgetInstrumentCatalogEntry] = []
        warnings: list[str] = []
        errors: list[str] = []
        refreshed_families: list[str] = []
        category_descriptors: list[BitgetMarketCapabilityMatrixRow] = []

        try:
            spot_rows = self._spot_symbol_rows()
            spot_entries = self._spot_catalog_entries(spot_rows)
            entries.extend(spot_entries)
            category_descriptors.append(
                self._category_descriptor(
                    market_family="spot",
                    entries=spot_entries,
                    metadata_source=endpoint_profile_for("spot").public_symbol_config_path,
                    reasons=(
                        [] if spot_entries else ["spot_category_not_exposed_by_current_metadata"]
                    ),
                )
            )
            refreshed_families.append("spot")
        except Exception as exc:
            errors.append(f"spot_discovery_failed:{exc}")
            spot_rows = []

        try:
            futures_rows = self._futures_contract_rows()
            futures_entries = self._futures_catalog_entries(futures_rows)
            entries.extend(futures_entries)
            for product_type in _FUTURES_PRODUCT_TYPES:
                per_product_entries = [
                    entry for entry in futures_entries if entry.product_type == product_type
                ]
                category_descriptors.append(
                    self._category_descriptor(
                        market_family="futures",
                        product_type=product_type,
                        entries=per_product_entries,
                        metadata_source=endpoint_profile_for("futures").public_symbol_config_path,
                        reasons=(
                            []
                            if per_product_entries
                            else [f"product_type_not_exposed_by_current_metadata:{product_type}"]
                        ),
                    )
                )
            refreshed_families.append("futures")
        except Exception as exc:
            errors.append(f"futures_discovery_failed:{exc}")

        try:
            margin_entries, margin_warnings = self._margin_catalog_entries(
                spot_rows=spot_rows,
                candidate_symbols=candidate_margin_symbols,
            )
            entries.extend(margin_entries)
            warnings.extend(margin_warnings)
            for margin_mode in ("isolated", "crossed"):
                per_mode_entries = [
                    entry
                    for entry in margin_entries
                    if entry.margin_account_mode == margin_mode
                ]
                profile = endpoint_profile_for("margin", margin_account_mode=margin_mode)
                reasons = []
                if not per_mode_entries:
                    reasons.append(
                        f"margin_{margin_mode}_category_not_exposed_by_current_account_or_metadata"
                    )
                category_descriptors.append(
                    self._category_descriptor(
                        market_family="margin",
                        margin_account_mode=margin_mode,
                        entries=per_mode_entries,
                        metadata_source=profile.private_account_assets_path
                        or profile.public_symbol_config_path,
                        reasons=reasons,
                    )
                )
            refreshed_families.append("margin")
        except Exception as exc:
            errors.append(f"margin_discovery_failed:{exc}")

        status = "ok"
        if errors and entries:
            status = "partial"
        elif errors and not entries:
            status = "error"
        return BitgetInstrumentCatalogSnapshot(
            snapshot_id=str(uuid4()),
            source_service=source_service,
            refresh_reason=refresh_reason,
            status=status,
            fetch_started_ts_ms=started,
            fetch_completed_ts_ms=int(time.time() * 1000),
            refreshed_families=refreshed_families,
            capability_matrix=build_capability_matrix(
                self._dedupe_catalog_entries(entries),
                category_descriptors=category_descriptors,
            ),
            entries=self._dedupe_catalog_entries(entries),
            warnings=warnings,
            errors=errors,
        )

    def discover_spot_symbols(
        self,
        *,
        symbol: str | None = None,
    ) -> list[BitgetInstrumentIdentity]:
        entries = self._spot_catalog_entries(self._spot_symbol_rows(symbol=symbol))
        return [entry.identity() for entry in entries]

    def discover_futures_contracts(
        self,
        *,
        symbol: str | None = None,
    ) -> list[BitgetInstrumentIdentity]:
        rows = self._futures_contract_rows(symbol=symbol)
        return [entry.identity() for entry in self._futures_catalog_entries(rows)]

    def discover_margin_symbols(
        self,
        *,
        candidate_symbols: Sequence[str] | None = None,
    ) -> list[BitgetInstrumentIdentity]:
        spot_rows = self._spot_symbol_rows()
        entries, _warnings = self._margin_catalog_entries(
            spot_rows=spot_rows,
            candidate_symbols=candidate_symbols,
        )
        return [entry.identity() for entry in entries]

    def _spot_symbol_rows(self, *, symbol: str | None = None) -> list[dict[str, Any]]:
        profile = endpoint_profile_for("spot")
        params = {"symbol": symbol or self._settings.symbol} if symbol else {}
        payload = self._public_json(profile.public_symbol_config_path, params=params)
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _spot_catalog_entries(
        self,
        rows: Sequence[dict[str, Any]],
    ) -> list[BitgetInstrumentCatalogEntry]:
        profile = endpoint_profile_for("spot")
        entries: list[BitgetInstrumentCatalogEntry] = []
        for row in rows:
            trading_status = str(row.get("status") or "unknown").strip().lower() or "unknown"
            eligibility = self._eligibility_flags(
                trading_enabled=trading_status_allows_trading(trading_status),
                subscribe_enabled=trading_status_allows_subscription(trading_status),
                execution_adapter_available=profile.private_place_order_path is not None,
            )
            entries.append(
                BitgetInstrumentCatalogEntry(
                    market_family="spot",
                    symbol=str(row.get("symbol") or self._settings.symbol),
                    symbol_aliases=[str(row.get("symbol") or self._settings.symbol)],
                    base_coin=str(row.get("baseCoin") or "") or None,
                    quote_coin=str(row.get("quoteCoin") or "") or None,
                    public_ws_inst_type=profile.public_ws_inst_type,
                    private_ws_inst_type=profile.public_ws_inst_type,
                    metadata_source=profile.public_symbol_config_path,
                    metadata_verified=True,
                    status=trading_status,
                    inventory_visible=eligibility["inventory_visible"],
                    analytics_eligible=eligibility["analytics_eligible"],
                    paper_shadow_eligible=eligibility["paper_shadow_eligible"],
                    live_execution_enabled=eligibility["live_execution_enabled"],
                    execution_disabled=eligibility["execution_disabled"],
                    trading_status=trading_status,
                    trading_enabled=eligibility["trading_enabled"],
                    subscribe_enabled=eligibility["subscribe_enabled"],
                    supports_reduce_only=profile.supports_reduce_only,
                    supports_long_short=profile.supports_long_short,
                    supports_shorting=profile.supports_shorting,
                    supports_leverage=profile.supports_leverage,
                    uses_spot_public_market_data=profile.uses_spot_public_market_data,
                    price_tick_size=self._spot_tick_size(row),
                    quantity_step=self._spot_quantity_step(row),
                    quantity_min=str(row.get("minTradeAmount") or "") or None,
                    quantity_max=str(row.get("maxTradeAmount") or "") or None,
                    min_notional_quote=str(row.get("minTradeUSDT") or "") or None,
                    price_precision=self._optional_int(row.get("pricePrecision")),
                    quantity_precision=self._optional_int(row.get("quantityPrecision")),
                    quote_precision=self._optional_int(row.get("quotePrecision")),
                    symbol_type="spot",
                    session_metadata={
                        "schedule": "24x7",
                        "timezone": "UTC",
                    },
                    refresh_ts_ms=int(time.time() * 1000),
                    raw_metadata=row,
                )
            )
        return entries

    def _futures_contract_rows(self, *, symbol: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        profile = endpoint_profile_for("futures")
        for product_type in _FUTURES_PRODUCT_TYPES:
            params: dict[str, str] = {"productType": product_type}
            if symbol:
                params["symbol"] = symbol
            payload = self._public_json(profile.public_symbol_config_path, params=params)
            data = payload.get("data")
            if not isinstance(data, list):
                continue
            for row in data:
                if not isinstance(row, dict):
                    continue
                enriched = dict(row)
                enriched.setdefault("productType", product_type)
                rows.append(enriched)
        return rows

    def _futures_catalog_entries(
        self,
        rows: Sequence[dict[str, Any]],
    ) -> list[BitgetInstrumentCatalogEntry]:
        profile = endpoint_profile_for("futures")
        entries: list[BitgetInstrumentCatalogEntry] = []
        for row in rows:
            product_type = str(row.get("productType") or "").strip().upper()
            if not product_type:
                continue
            trading_status = (
                str(row.get("symbolStatus") or row.get("status") or "unknown").strip().lower()
                or "unknown"
            )
            eligibility = self._eligibility_flags(
                trading_enabled=trading_status_allows_trading(trading_status),
                subscribe_enabled=trading_status_allows_subscription(trading_status),
                execution_adapter_available=profile.private_place_order_path is not None,
            )
            margin_coin = self._first_list_value(row.get("supportMarginCoins")) or str(
                row.get("marginCoin") or ""
            )
            session_metadata = {
                "schedule": "24x7",
                "timezone": "UTC",
                "symbol_type": str(row.get("symbolType") or "") or None,
                "off_time": self._optional_int(row.get("offTime")),
                "limit_open_time": self._optional_int(row.get("limitOpenTime")),
                "delivery_time": self._optional_int(row.get("deliveryTime")),
                "delivery_start_time": self._optional_int(row.get("deliveryStartTime")),
                "launch_time": self._optional_int(row.get("launchTime")),
                "maintain_time": self._optional_int(row.get("maintainTime")),
            }
            entries.append(
                BitgetInstrumentCatalogEntry(
                    market_family="futures",
                    symbol=str(row.get("symbol") or self._settings.symbol),
                    symbol_aliases=[str(row.get("symbol") or self._settings.symbol)],
                    product_type=product_type,
                    margin_coin=margin_coin or None,
                    base_coin=str(row.get("baseCoin") or "") or None,
                    quote_coin=str(row.get("quoteCoin") or "") or None,
                    settle_coin=str(row.get("settleCoin") or margin_coin or "") or None,
                    margin_account_mode="isolated",
                    public_ws_inst_type=product_type,
                    private_ws_inst_type=product_type,
                    metadata_source=profile.public_symbol_config_path,
                    metadata_verified=True,
                    status=trading_status,
                    inventory_visible=eligibility["inventory_visible"],
                    analytics_eligible=eligibility["analytics_eligible"],
                    paper_shadow_eligible=eligibility["paper_shadow_eligible"],
                    live_execution_enabled=eligibility["live_execution_enabled"],
                    execution_disabled=eligibility["execution_disabled"],
                    trading_status=trading_status,
                    trading_enabled=eligibility["trading_enabled"],
                    subscribe_enabled=eligibility["subscribe_enabled"],
                    supports_funding=profile.supports_funding,
                    supports_open_interest=profile.supports_open_interest,
                    supports_reduce_only=profile.supports_reduce_only,
                    supports_long_short=profile.supports_long_short,
                    supports_shorting=profile.supports_shorting,
                    supports_leverage=profile.supports_leverage,
                    price_tick_size=str(row.get("priceEndStep") or "") or None,
                    quantity_step=str(row.get("sizeMultiplier") or "") or None,
                    quantity_min=str(row.get("minTradeNum") or "") or None,
                    quantity_max=str(row.get("maxOrderQty") or "") or None,
                    market_order_quantity_max=str(row.get("maxMarketOrderQty") or "") or None,
                    min_notional_quote=str(row.get("minTradeUSDT") or "") or None,
                    price_precision=self._optional_int(row.get("pricePlace")),
                    quantity_precision=self._optional_int(row.get("volumePlace")),
                    leverage_min=self._optional_int(row.get("minLever")),
                    leverage_max=self._optional_int(row.get("maxLever")),
                    funding_interval_hours=self._optional_int(row.get("fundInterval")),
                    symbol_type=str(row.get("symbolType") or "") or None,
                    supported_margin_coins=list(row.get("supportMarginCoins") or []),
                    session_metadata={k: v for k, v in session_metadata.items() if v is not None},
                    refresh_ts_ms=int(time.time() * 1000),
                    raw_metadata=row,
                )
            )
        return entries

    def _margin_catalog_entries(
        self,
        *,
        spot_rows: Sequence[dict[str, Any]],
        candidate_symbols: Sequence[str] | None,
    ) -> tuple[list[BitgetInstrumentCatalogEntry], list[str]]:
        warnings: list[str] = []
        spot_by_symbol = {
            str(row.get("symbol") or "").strip().upper(): row
            for row in spot_rows
            if isinstance(row, dict) and str(row.get("symbol") or "").strip()
        }
        entries: list[BitgetInstrumentCatalogEntry] = []
        isolated_entries = self._margin_mode_catalog_entries(
            margin_account_mode="isolated",
            spot_by_symbol=spot_by_symbol,
        )
        entries.extend(isolated_entries)

        cross_entries = self._margin_mode_catalog_entries(
            margin_account_mode="crossed",
            spot_by_symbol=spot_by_symbol,
        )
        if cross_entries:
            entries.extend(cross_entries)
        else:
            warnings.append("margin_crossed_symbol_universe_not_exposed_by_current_endpoints")

        if candidate_symbols:
            for symbol in candidate_symbols:
                normalized = str(symbol).strip().upper()
                if not normalized:
                    continue
                if normalized not in spot_by_symbol:
                    warnings.append(f"candidate_symbol_not_in_spot_metadata:{normalized}")
        return self._dedupe_catalog_entries(entries), warnings

    def _margin_mode_catalog_entries(
        self,
        *,
        margin_account_mode: MarginAccountMode,
        spot_by_symbol: dict[str, dict[str, Any]],
    ) -> list[BitgetInstrumentCatalogEntry]:
        profile = endpoint_profile_for("margin", margin_account_mode=margin_account_mode)
        if not profile.private_account_assets_path:
            return []
        payload = self._private_json(
            profile.private_account_assets_path,
            params={},
        )
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        symbols = {
            str(row.get("symbol") or "").strip().upper()
            for row in data
            if isinstance(row, dict) and str(row.get("symbol") or "").strip()
        }
        entries: list[BitgetInstrumentCatalogEntry] = []
        for symbol in sorted(symbols):
            spot_row = spot_by_symbol.get(symbol)
            if not spot_row:
                continue
            spot_status = str(spot_row.get("status") or "unknown").strip().lower() or "unknown"
            trading_status = f"{spot_status}_account_visible"
            eligibility = self._eligibility_flags(
                trading_enabled=trading_status_allows_trading(spot_status),
                subscribe_enabled=trading_status_allows_subscription(spot_status),
                execution_adapter_available=profile.private_place_order_path is not None,
            )
            entries.append(
                BitgetInstrumentCatalogEntry(
                    market_family="margin",
                    symbol=symbol,
                    symbol_aliases=[symbol],
                    margin_account_mode=margin_account_mode,
                    public_ws_inst_type=profile.public_ws_inst_type,
                    private_ws_inst_type=profile.private_ws_inst_type,
                    metadata_source=profile.private_account_assets_path,
                    metadata_verified=True,
                    status=trading_status,
                    inventory_visible=eligibility["inventory_visible"],
                    analytics_eligible=eligibility["analytics_eligible"],
                    paper_shadow_eligible=eligibility["paper_shadow_eligible"],
                    live_execution_enabled=eligibility["live_execution_enabled"],
                    execution_disabled=eligibility["execution_disabled"],
                    trading_status=trading_status,
                    trading_enabled=eligibility["trading_enabled"],
                    subscribe_enabled=eligibility["subscribe_enabled"],
                    supports_reduce_only=profile.supports_reduce_only,
                    supports_long_short=profile.supports_long_short,
                    supports_shorting=profile.supports_shorting,
                    supports_leverage=profile.supports_leverage,
                    uses_spot_public_market_data=profile.uses_spot_public_market_data,
                    base_coin=str(spot_row.get("baseCoin") or "") or None,
                    quote_coin=str(spot_row.get("quoteCoin") or "") or None,
                    price_tick_size=self._spot_tick_size(spot_row),
                    quantity_step=self._spot_quantity_step(spot_row),
                    quantity_min=str(spot_row.get("minTradeAmount") or "") or None,
                    quantity_max=str(spot_row.get("maxTradeAmount") or "") or None,
                    min_notional_quote=str(spot_row.get("minTradeUSDT") or "") or None,
                    price_precision=self._optional_int(spot_row.get("pricePrecision")),
                    quantity_precision=self._optional_int(spot_row.get("quantityPrecision")),
                    quote_precision=self._optional_int(spot_row.get("quotePrecision")),
                    symbol_type="margin",
                    session_metadata={
                        "schedule": "24x7",
                        "timezone": "UTC",
                    },
                    refresh_ts_ms=int(time.time() * 1000),
                    raw_metadata=spot_row,
                )
            )
        return entries

    def _dedupe_catalog_entries(
        self,
        entries: Sequence[BitgetInstrumentCatalogEntry],
    ) -> list[BitgetInstrumentCatalogEntry]:
        deduped: dict[str, BitgetInstrumentCatalogEntry] = {
            entry.canonical_instrument_id or entry.instrument_key: entry for entry in entries
        }
        return list(deduped.values())

    def _eligibility_flags(
        self,
        *,
        trading_enabled: bool,
        subscribe_enabled: bool,
        execution_adapter_available: bool,
    ) -> dict[str, bool]:
        inventory_visible = True
        analytics_eligible = bool(subscribe_enabled)
        paper_shadow_eligible = bool(trading_enabled and execution_adapter_available)
        live_execution_enabled = bool(trading_enabled and execution_adapter_available)
        execution_disabled = inventory_visible and analytics_eligible and not live_execution_enabled
        return {
            "inventory_visible": inventory_visible,
            "analytics_eligible": analytics_eligible,
            "paper_shadow_eligible": paper_shadow_eligible,
            "live_execution_enabled": live_execution_enabled,
            "execution_disabled": execution_disabled,
            "trading_enabled": bool(trading_enabled),
            "subscribe_enabled": bool(subscribe_enabled),
        }

    def _category_descriptor(
        self,
        *,
        market_family: str,
        entries: Sequence[BitgetInstrumentCatalogEntry],
        metadata_source: str,
        product_type: str | None = None,
        margin_account_mode: str = "cash",
        reasons: Sequence[str] = (),
    ) -> BitgetMarketCapabilityMatrixRow:
        inventory_visible = any(entry.inventory_visible for entry in entries)
        analytics_eligible = any(entry.analytics_eligible for entry in entries)
        paper_shadow_eligible = any(entry.paper_shadow_eligible for entry in entries)
        live_execution_enabled = any(entry.live_execution_enabled for entry in entries)
        metadata_verified = any(entry.metadata_verified for entry in entries)
        supports_funding = any(entry.supports_funding for entry in entries)
        supports_open_interest = any(entry.supports_open_interest for entry in entries)
        supports_long_short = any(entry.supports_long_short for entry in entries)
        supports_shorting = any(entry.supports_shorting for entry in entries)
        supports_reduce_only = any(entry.supports_reduce_only for entry in entries)
        supports_leverage = any(entry.supports_leverage for entry in entries)
        uses_spot_public_market_data = any(
            entry.uses_spot_public_market_data for entry in entries
        )
        if not entries:
            profile = endpoint_profile_for(
                market_family, margin_account_mode=margin_account_mode
            )
            supports_funding = profile.supports_funding
            supports_open_interest = profile.supports_open_interest
            supports_long_short = profile.supports_long_short
            supports_shorting = profile.supports_shorting
            supports_reduce_only = profile.supports_reduce_only
            supports_leverage = profile.supports_leverage
            uses_spot_public_market_data = profile.uses_spot_public_market_data
        return BitgetMarketCapabilityMatrixRow(
            venue="bitget",
            market_family=market_family,
            product_type=product_type,
            margin_account_mode=margin_account_mode,
            metadata_source=metadata_source,
            metadata_verified=metadata_verified,
            inventory_visible=inventory_visible,
            analytics_eligible=analytics_eligible,
            paper_shadow_eligible=paper_shadow_eligible,
            live_execution_enabled=live_execution_enabled,
            execution_disabled=inventory_visible and analytics_eligible and not live_execution_enabled,
            supports_funding=supports_funding,
            supports_open_interest=supports_open_interest,
            supports_long_short=supports_long_short,
            supports_shorting=supports_shorting,
            supports_reduce_only=supports_reduce_only,
            supports_leverage=supports_leverage,
            uses_spot_public_market_data=uses_spot_public_market_data,
            reasons=list(reasons),
        )

    def _spot_tick_size(self, row: dict[str, Any]) -> str | None:
        precision = self._optional_int(row.get("pricePrecision"))
        if precision is None:
            return None
        return format(10 ** (-precision), "f")

    def _spot_quantity_step(self, row: dict[str, Any]) -> str | None:
        precision = self._optional_int(row.get("quantityPrecision"))
        if precision is None:
            return None
        return format(10 ** (-precision), "f")

    def _first_list_value(self, value: object) -> str | None:
        if isinstance(value, list):
            for item in value:
                normalized = str(item).strip().upper()
                if normalized:
                    return normalized
        return None

    def _optional_int(self, value: object) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def _public_json(
        self,
        path: str,
        *,
        params: dict[str, str],
    ) -> dict[str, Any]:
        url = f"{self._settings.effective_rest_base_url}{path}"
        with httpx.Client(timeout=self._timeout_sec) as client:
            response = client.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Bitget discovery response muss ein JSON-Objekt sein")
        if payload.get("code") not in (None, "00000"):
            raise ValueError(f"Bitget discovery response code not ok: {payload.get('code')}")
        return payload

    def _private_json(
        self,
        path: str,
        *,
        params: dict[str, str],
    ) -> dict[str, Any]:
        query_string = build_query_string(params)
        timestamp_ms = int(time.time() * 1000)
        headers = build_private_rest_headers(
            self._settings,
            timestamp_ms=timestamp_ms,
            method="GET",
            request_path=path,
            query_string=query_string,
            body="",
        )
        url = f"{self._settings.effective_rest_base_url}{path}"
        with httpx.Client(timeout=self._timeout_sec) as client:
            response = client.get(
                url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Bitget private discovery response muss ein JSON-Objekt sein")
        if payload.get("code") not in (None, "00000"):
            raise ValueError(
                f"Bitget private discovery response code not ok: {payload.get('code')}"
            )
        return payload
