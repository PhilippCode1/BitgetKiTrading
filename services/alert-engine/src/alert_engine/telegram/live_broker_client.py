from __future__ import annotations

import logging
from typing import Any

import httpx

from alert_engine.config import Settings
from shared_py.service_auth import INTERNAL_SERVICE_HEADER

logger = logging.getLogger("alert_engine.live_broker_client")


class LiveBrokerOpsClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        base = str(settings.live_broker_ops_base_url or "").strip().rstrip("/")
        self._base = base
        self._key = str(settings.service_internal_api_key or "").strip()

    def configured(self) -> bool:
        return bool(self._base and self._key)

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_SERVICE_HEADER: self._key, "Content-Type": "application/json"}

    def get_execution_telegram_summary(self, execution_id: str) -> tuple[int, dict[str, Any]]:
        url = f"{self._base}/live-broker/executions/{execution_id}/telegram-summary"
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(url, headers=self._headers())
                return r.status_code, dict(r.json() if r.content else {})
        except httpx.HTTPError as exc:
            logger.warning("live-broker GET telegram-summary failed: %s", exc)
            return 0, {"error": str(exc)}

    def post_operator_release(
        self,
        execution_id: str,
        *,
        audit: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self._base}/live-broker/executions/{execution_id}/operator-release"
        body = {"source": "telegram_operator", "audit": audit}
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, headers=self._headers(), json=body)
                try:
                    data = r.json() if r.content else {}
                except Exception:
                    data = {"raw": r.text[:500]}
                return r.status_code, dict(data) if isinstance(data, dict) else {"data": data}
        except httpx.HTTPError as exc:
            logger.warning("live-broker POST operator-release failed: %s", exc)
            return 0, {"error": str(exc)}

    def get_recent_decisions(self, limit: int = 15) -> tuple[int, dict[str, Any]]:
        url = f"{self._base}/live-broker/decisions/recent"
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(url, params={"limit": limit}, headers=self._headers())
                return r.status_code, dict(r.json() if r.content else {})
        except httpx.HTTPError as exc:
            logger.warning("live-broker GET decisions/recent failed: %s", exc)
            return 0, {"error": str(exc)}

    def post_emergency_flatten(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        url = f"{self._base}/live-broker/orders/emergency-flatten"
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, headers=self._headers(), json=body)
                try:
                    data = r.json() if r.content else {}
                except Exception:
                    data = {"raw": r.text[:500]}
                return r.status_code, dict(data) if isinstance(data, dict) else {"data": data}
        except httpx.HTTPError as exc:
            logger.warning("live-broker POST emergency-flatten failed: %s", exc)
            return 0, {"error": str(exc)}
