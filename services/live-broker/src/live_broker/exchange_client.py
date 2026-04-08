from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from shared_py.bitget import build_rest_headers
from shared_py.bitget.instruments import MarginAccountMode, endpoint_profile_for

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings
    from live_broker.execution.models import ExecutionIntentRequest
    from live_broker.private_rest import BitgetPrivateRestClient

logger = logging.getLogger("live_broker.exchange_client")

_PRIVATE_DETAIL_DE: dict[str, str] = {
    "missing_api_key_or_secret": (
        "API-Key oder Secret fehlt. Demo: BITGET_DEMO_ENABLED=true sowie BITGET_DEMO_API_KEY und "
        "BITGET_DEMO_API_SECRET. Live: BITGET_API_KEY und BITGET_API_SECRET."
    ),
    "missing_api_passphrase": (
        "API-Passphrase fehlt (Bitget verlangt Key + Secret + Passphrase). "
        "Demo: BITGET_DEMO_API_PASSPHRASE. Live: BITGET_API_PASSPHRASE."
    ),
    "ok": "Schluessel tripel vollstaendig (Key, Secret, Passphrase).",
    "not_required": "Privater Zugriff ist fuer diesen Lauf nicht erforderlich.",
}


class BitgetExchangeClient:
    def __init__(self, settings: "LiveBrokerSettings") -> None:
        self._settings = settings

    def describe(self) -> dict[str, Any]:
        return {
            "effective_rest_base_url": self._settings.effective_rest_base_url,
            "effective_ws_private_url": self._settings.effective_ws_private_url,
            "market_family": self._settings.market_family,
            "product_type": self._settings.product_type,
            "margin_coin": self._settings.effective_margin_coin,
            "margin_account_mode": self._settings.margin_account_mode,
            "locale": self._settings.bitget_rest_locale,
            "symbol": self._settings.symbol,
            "demo_mode": self._settings.bitget_demo_enabled,
            "live_broker_enabled": self._settings.live_broker_enabled,
            "live_allow_order_submit": self._settings.live_allow_order_submit,
        }

    def private_api_configured(self) -> tuple[bool, str]:
        if not self._settings.effective_api_key or not self._settings.effective_api_secret:
            return False, "missing_api_key_or_secret"
        if not self._settings.effective_api_passphrase:
            return False, "missing_api_passphrase"
        return True, "ok"

    def probe_exchange(self, private_rest: "BitgetPrivateRestClient | None" = None) -> dict[str, Any]:
        public_api_ok = False
        public_detail = "not_checked"
        try:
            market_snapshot = self.get_market_snapshot(self._settings.symbol)
            public_api_ok = True
            public_detail = "ok"
        except Exception as exc:
            market_snapshot = {}
            public_detail = str(exc)[:200]
            logger.warning("bitget public probe failed: %s", exc)

        private_ok, private_detail = self.private_api_configured()
        private_detail_de = _PRIVATE_DETAIL_DE.get(private_detail, private_detail)
        out: dict[str, Any] = {
            **self.describe(),
            "public_api_ok": public_api_ok,
            "public_detail": public_detail,
            "private_api_configured": private_ok,
            "private_detail": private_detail,
            "private_detail_de": private_detail_de,
            "private_auth_ok": None,
            "private_auth_detail": None,
            "private_auth_detail_de": None,
            "private_auth_classification": None,
            "private_auth_exchange_code": None,
            "market_snapshot": market_snapshot,
        }
        if private_rest is not None:
            out["credential_profile"] = "demo" if self._settings.bitget_demo_enabled else "live"
            out["credential_isolation_relaxed"] = bool(
                getattr(self._settings, "bitget_relax_credential_isolation", False)
            )
            out["paptrading_header_active"] = bool(self._settings.bitget_demo_enabled)
            out["bitget_private_rest"] = private_rest.state_snapshot()
        if private_ok and private_rest is not None:
            auth = private_rest.probe_private_access()
            out["private_auth_ok"] = bool(auth.get("private_auth_ok"))
            out["private_auth_detail"] = auth.get("private_auth_detail")
            out["private_auth_detail_de"] = auth.get("private_auth_detail_de")
            out["private_auth_classification"] = auth.get("private_auth_classification")
            out["private_auth_exchange_code"] = auth.get("private_auth_exchange_code")
        return out

    def get_market_snapshot(self, symbol: str) -> dict[str, Any]:
        endpoint = self._settings.endpoint_profile.public_ticker_path
        url = f"{self._settings.effective_rest_base_url}{endpoint}"
        params = {"symbol": symbol}
        if self._settings.rest_product_type_param:
            params["productType"] = self._settings.rest_product_type_param
        headers = build_rest_headers(
            self._settings,
            {
                "Accept": "application/json",
                "User-Agent": "live-broker/1.0",
            },
        )
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            item = None
        if not isinstance(item, dict):
            raise ValueError("bitget response data fehlt")
        return {
            "symbol": symbol,
            "market_family": self._settings.market_family,
            "last_price": item.get("price") or item.get("lastPr"),
            "mark_price": item.get("markPrice"),
            "index_price": item.get("indexPrice"),
            "bid_price": item.get("bidPr"),
            "ask_price": item.get("askPr"),
            "request_time": payload.get("requestTime")
            if isinstance(payload, dict)
            else None,
        }

    def get_market_snapshot_for_family(
        self,
        symbol: str,
        *,
        market_family: str,
        product_type: str | None = None,
        margin_account_mode: str | None = None,
    ) -> dict[str, Any]:
        """Public Ticker fuer beliebige Marktfamilie (kein Private-Auth)."""
        fam = str(market_family).lower()
        mode: MarginAccountMode = "cash"
        if fam == "margin":
            raw = str(margin_account_mode or self._settings.margin_account_mode).lower()
            mode = "crossed" if raw == "crossed" else "isolated"
        profile = endpoint_profile_for(fam, margin_account_mode=mode)
        endpoint = profile.public_ticker_path
        url = f"{self._settings.effective_rest_base_url}{endpoint}"
        params: dict[str, str] = {"symbol": symbol}
        if fam == "futures":
            pt = (product_type or self._settings.product_type or "").strip()
            if pt:
                params["productType"] = pt.lower().replace("_", "-")
            elif self._settings.rest_product_type_param:
                params["productType"] = str(self._settings.rest_product_type_param)
        headers = build_rest_headers(
            self._settings,
            {
                "Accept": "application/json",
                "User-Agent": "live-broker/1.0",
            },
        )
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            item = None
        if not isinstance(item, dict):
            raise ValueError("bitget response data fehlt")
        return {
            "symbol": symbol,
            "market_family": fam,
            "last_price": item.get("price") or item.get("lastPr"),
            "mark_price": item.get("markPrice"),
            "index_price": item.get("indexPrice"),
            "bid_price": item.get("bidPr"),
            "ask_price": item.get("askPr"),
            "request_time": payload.get("requestTime")
            if isinstance(payload, dict)
            else None,
        }

    def build_order_preview(self, intent: "ExecutionIntentRequest") -> dict[str, Any]:
        side = "buy" if intent.direction == "long" else "sell"
        return {
            "rest_base_url": self._settings.effective_rest_base_url,
            "ws_private_url": self._settings.effective_ws_private_url,
            "market_family": self._settings.market_family,
            "symbol": intent.symbol,
            "product_type": self._settings.product_type,
            "margin_coin": self._settings.effective_margin_coin,
            "margin_account_mode": self._settings.margin_account_mode,
            "side": side,
            "order_type": intent.order_type,
            "qty_base": intent.qty_base,
            "leverage": intent.leverage,
            "entry_price": intent.entry_price,
            "stop_loss": intent.stop_loss,
            "take_profit": intent.take_profit,
            "requested_runtime_mode": intent.requested_runtime_mode,
            "demo_mode": self._settings.bitget_demo_enabled,
            "instrument": self._settings.instrument_identity().model_dump(mode="json"),
        }
