from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
import psycopg
from shared_py.bitget import BitgetInstrumentCatalog, UnknownInstrumentError
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry

from paper_broker.config import PaperBrokerSettings
from paper_broker.engine.exceptions import InstrumentNotFoundError
from paper_broker.engine.instrument_context import instrument_hints_from_signal
from paper_broker.paths import fixtures_dir

logger = logging.getLogger("paper_broker.contract_config")


@dataclass(frozen=True)
class ContractConfigView:
    symbol: str
    product_type: str
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    size_multiplier: Decimal
    fund_interval_hours: int
    max_lever: int
    price_end_step: Decimal
    raw: dict[str, Any]


def _dec(x: Any, default: str = "0") -> Decimal:
    if x is None or x == "":
        return Decimal(default)
    return Decimal(str(x))


class ContractConfigProvider:
    def __init__(
        self,
        settings: PaperBrokerSettings,
        *,
        catalog: BitgetInstrumentCatalog | None = None,
    ) -> None:
        self._settings = settings
        self._catalog = catalog

    def get(
        self,
        symbol: str,
        conn: psycopg.Connection[Any] | None = None,
        *,
        signal_payload: dict[str, Any] | None = None,
    ) -> ContractConfigView:
        mode = self._settings.paper_contract_config_mode.strip().lower()
        entry: BitgetInstrumentCatalogEntry | None = None
        if self._catalog is not None:
            entry = self._catalog_entry(symbol, signal_payload=signal_payload)
        if mode == "live":
            return self._fetch_live(symbol, conn, entry=entry)
        if entry is not None:
            return self._view_from_catalog_entry(entry)
        if self._fixture_fallback_allowed():
            return self._from_fixture_file(symbol, entry=None)
        raise InstrumentNotFoundError(
            f"instrument not in Postgres catalog: {symbol!r} "
            "(Katalog / PAPER_CONTRACT_CONFIG_MODE / APP_ENV: fixture in local/dev)"
        )

    def _fixture_fallback_allowed(self) -> bool:
        app_env = str(getattr(self._settings, "app_env", "") or "").strip().lower()
        production = bool(getattr(self._settings, "production", False))
        return not (production or app_env in {"shadow", "production"})

    def _fallback_or_raise(
        self,
        symbol: str,
        *,
        reason: str,
        entry: BitgetInstrumentCatalogEntry | None = None,
        exc: Exception | None = None,
    ) -> ContractConfigView:
        if self._fixture_fallback_allowed():
            if exc is not None:
                logger.warning("%s, fallback fixture: %s", reason, exc)
            else:
                logger.warning("%s, fallback fixture", reason)
            return self._from_fixture_file(symbol, entry=entry)
        detail = f"{reason}: {exc}" if exc is not None else reason
        msg = f"paper contract config live fetch failed in prod-like mode for {symbol}"
        raise RuntimeError(f"{msg}: {detail}")

    def _view_from_catalog_entry(
        self, entry: BitgetInstrumentCatalogEntry
    ) -> ContractConfigView:
        """Katalog (DB/Discovery) -> ContractConfigView; kein generisches BTC-JSON."""
        data = self._bitget_shaped_dict_from_entry(entry)
        return self._parse_dict(data, str(entry.symbol), entry=entry)

    def _bitget_shaped_dict_from_entry(
        self,
        entry: BitgetInstrumentCatalogEntry,
    ) -> dict[str, Any]:
        """
        Baut ein Bitget-REST-ähnliches Dict fuer _parse_dict aus raw_metadata
        oder Katalog-Feldern (quantity_step, price_tick_size, ...).
        """
        rm: dict[str, Any] = (
            dict(entry.raw_metadata) if isinstance(entry.raw_metadata, dict) else {}
        )
        if any(
            k in rm
            for k in (
                "sizeMultiplier",
                "makerFeeRate",
                "takerFeeRate",
                "minTradeUSDT",
                "priceEndStep",
                "productType",
            )
        ):
            return {**rm, "symbol": entry.symbol}
        mkr = str(rm.get("makerFeeRate") or self._settings.paper_default_maker_fee)
        tkr = str(rm.get("takerFeeRate") or self._settings.paper_default_taker_fee)
        if entry.market_family == "futures":
            ptype = (
                entry.product_type
                or self._settings.bitget_product_type
                or "USDT-FUTURES"
            )
            return {
                "symbol": entry.symbol,
                "productType": ptype.strip().upper(),
                "makerFeeRate": mkr,
                "takerFeeRate": tkr,
                "sizeMultiplier": str(
                    entry.quantity_step or rm.get("sizeMultiplier") or "1"
                ),
                "fundInterval": str(
                    entry.funding_interval_hours
                    if entry.funding_interval_hours is not None
                    else 8
                ),
                "maxLever": str(
                    entry.leverage_max
                    if entry.leverage_max is not None
                    else self._settings.paper_max_leverage
                ),
                "priceEndStep": str(
                    entry.price_tick_size
                    or rm.get("priceEndStep")
                    or (entry.raw_metadata or {}).get("priceEndStep")
                    or "0.1"
                ),
                "minTradeNum": str(
                    entry.quantity_min
                    or (entry.raw_metadata or {}).get("minTradeNum")
                    or "0.001"
                ),
                "minTradeUSDT": str(
                    entry.min_notional_quote
                    or (entry.raw_metadata or {}).get("minTradeUSDT")
                    or "5"
                ),
            }
        qstep = str(entry.quantity_step or rm.get("minTradeNum") or "0.0001")
        ptick = str(
            entry.price_tick_size
            or rm.get("priceEndStep")
            or rm.get("pricePrecision")
            or "0.1"
        )
        mf = self._settings.bitget_market_family
        ptype = rm.get("productType") or (str(mf).upper() if mf else "SPOT")
        return {
            "symbol": entry.symbol,
            "productType": ptype,
            "makerFeeRate": mkr,
            "takerFeeRate": tkr,
            "sizeMultiplier": qstep,
            "priceEndStep": ptick,
        }

    def _from_fixture_file(
        self,
        symbol: str,
        *,
        entry: BitgetInstrumentCatalogEntry | None = None,
    ) -> ContractConfigView:
        fam = (
            str(entry.market_family).lower()
            if entry is not None
            else str(self._settings.bitget_market_family).lower()
        )
        candidates = [
            fixtures_dir() / f"contract_config_{fam}_{symbol.lower()}.json",
            fixtures_dir() / f"contract_config_{symbol.lower()}.json",
        ]
        path = next((item for item in candidates if item.is_file()), None)
        if path is None or not path.is_file():
            raise FileNotFoundError(
                f"keine contract_config-JSON in fixtures fuer symbol={symbol!r} "
                "(per-family/symbol-Datei, oder Katalog / live mode)"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._parse_dict(data, symbol, entry=entry)

    def _parse_dict(
        self,
        data: dict[str, Any],
        symbol: str,
        *,
        entry: BitgetInstrumentCatalogEntry | None = None,
    ) -> ContractConfigView:
        sym = str(data.get("symbol") or symbol).upper()
        if entry is not None:
            mf0 = entry.market_family
        else:
            mf0 = self._settings.bitget_market_family
        if mf0 == "futures":
            pdef = self._settings.bitget_product_type
            pt0 = str(
                data.get("productType")
                or (entry.product_type if entry is not None else pdef)
            ).upper()
        else:
            pt0 = self._settings.bitget_market_family.upper()
        default_max_lever = (
            "1" if mf0 == "spot" else str(self._settings.paper_max_leverage)
        )
        return ContractConfigView(
            symbol=sym,
            product_type=pt0,
            maker_fee_rate=_dec(
                data.get("makerFeeRate"), self._settings.paper_default_maker_fee
            ),
            taker_fee_rate=_dec(
                data.get("takerFeeRate"), self._settings.paper_default_taker_fee
            ),
            size_multiplier=_dec(data.get("sizeMultiplier"), "1"),
            fund_interval_hours=int(
                Decimal(
                    str(
                        data.get("fundInterval")
                        or ("8" if mf0 == "futures" else "0")
                    )
                )
            ),
            max_lever=int(Decimal(str(data.get("maxLever") or default_max_lever))),
            price_end_step=_dec(
                data.get("priceEndStep"),
                str(data.get("pricePrecision") or "0.1"),
            ),
            raw={
                **dict(data),
                **(
                    {
                        "catalog_refresh_ts_ms": entry.refresh_ts_ms,
                        "catalog_canonical_instrument_id": (
                            entry.canonical_instrument_id
                        ),
                        "instrument_catalog_entry": entry.model_dump(mode="json"),
                    }
                    if entry is not None
                    else {}
                ),
            },
        )

    def _fetch_live(
        self,
        symbol: str,
        conn: psycopg.Connection[Any] | None,
        *,
        entry: BitgetInstrumentCatalogEntry | None = None,
    ) -> ContractConfigView:
        base = self._settings.bitget_api_base_url.rstrip("/")
        if entry is not None and not entry.subscribe_enabled:
            raise ValueError(
                "instrument not subscribable in catalog: "
                f"{entry.canonical_instrument_id}"
            )
        if entry is not None:
            family = entry.market_family
        else:
            family = self._settings.bitget_market_family
        endpoint_profile = (
            self._settings.endpoint_profile
            if entry is None
            else self._settings.endpoint_profile
        )
        url = f"{base}{endpoint_profile.public_symbol_config_path}"
        params = {"symbol": symbol}
        if entry is not None and entry.product_type:
            params["productType"] = entry.product_type
        elif self._settings.rest_product_type_param:
            params["productType"] = self._settings.bitget_product_type
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                body = r.json()
        except Exception as exc:
            return self._fallback_or_raise(
                symbol,
                reason="live contract fetch failed",
                entry=entry,
                exc=exc,
            )

        data_list = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data_list, list) or not data_list:
            return self._fallback_or_raise(
                symbol,
                reason="unexpected contracts response",
                entry=entry,
            )
        su = symbol.upper()
        row = next(
            (
                x
                for x in data_list
                if isinstance(x, dict) and str(x.get("symbol", "")).upper() == su
            ),
            data_list[0],
        )
        if not isinstance(row, dict):
            return self._fallback_or_raise(
                symbol,
                reason="contracts response row invalid",
                entry=entry,
            )
        if family in {"spot", "margin"} and "productType" not in row:
            row = {
                **row,
                "productType": family.upper(),
            }
        view = self._parse_dict(row, symbol, entry=entry)
        if conn is not None:
            self._persist_snapshot(conn, view)
        return view

    def _catalog_entry(
        self,
        symbol: str,
        *,
        signal_payload: dict[str, Any] | None = None,
    ) -> BitgetInstrumentCatalogEntry | None:
        if self._catalog is None:
            return None
        hints = instrument_hints_from_signal(signal_payload)
        bmf = str(self._settings.bitget_market_family or "").lower()
        mf = hints.get("market_family") or bmf
        pt = hints.get("product_type")
        if pt is None and mf == "futures":
            pt = str(self._settings.bitget_product_type).strip().upper() or None
        mm = hints.get("margin_account_mode")
        if mm is None and mf == "margin":
            mm = str(self._settings.bitget_margin_account_mode).lower()
        try:
            return self._catalog.resolve(
                symbol=symbol,
                market_family=mf,
                product_type=pt,
                margin_account_mode=mm,
                refresh_if_missing=False,
            )
        except UnknownInstrumentError as exc:
            raise InstrumentNotFoundError(str(exc)) from exc

    def _persist_snapshot(
        self, conn: psycopg.Connection[Any], v: ContractConfigView
    ) -> None:
        import time

        ts = int(time.time() * 1000)
        conn.execute(
            """
            INSERT INTO paper.contract_config_snapshots (
                symbol, product_type, maker_fee_rate, taker_fee_rate, size_multiplier,
                fund_interval_hours, max_lever, raw_json, captured_ts_ms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                v.symbol,
                v.product_type,
                str(v.maker_fee_rate),
                str(v.taker_fee_rate),
                str(v.size_multiplier),
                v.fund_interval_hours,
                v.max_lever,
                json.dumps(v.raw, separators=(",", ":"), ensure_ascii=False),
                ts,
            ),
        )

    def effective_fees(self, cfg: ContractConfigView) -> tuple[Decimal, Decimal]:
        if self._settings.paper_fee_source.strip().lower() == "env":
            return (
                Decimal(self._settings.paper_default_maker_fee),
                Decimal(self._settings.paper_default_taker_fee),
            )
        return cfg.maker_fee_rate, cfg.taker_fee_rate
