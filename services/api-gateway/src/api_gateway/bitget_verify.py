"""
Echte Verifikation der Bitget API-Keys fuer den Go-Live Preflight.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import httpx
from shared_py.bitget import BitgetSettings, build_private_rest_headers
from shared_py.tenant_exchange_credentials import (
    BitgetCredentialBundle,
    resolve_bitget_credentials_for_tenant,
)

logger = logging.getLogger("api_gateway.bitget_verify")


def _mock_verify_active() -> bool:
    if os.environ.get("GATEWAY_MOCK_BITGET_VERIFY_FAIL") == "true":
        return False
    return True


def _ping_bitget_with_bundle(bundle: BitgetCredentialBundle) -> bool:
    try:
        settings = BitgetSettings()
        base_url = settings.effective_rest_base_url
        path = "/api/v2/spot/account/assets"
        timestamp_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        headers = build_private_rest_headers(
            settings,
            timestamp_ms=timestamp_ms,
            method="GET",
            request_path=path,
            api_key=bundle.api_key,
            api_secret=bundle.api_secret,
            api_passphrase=bundle.api_passphrase,
        )
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url}{path}", headers=headers)
            if response.status_code == 401:
                logger.warning(
                    "Bitget API-Ping: 401 Unauthorized (Keys oder Passphrase ungueltig)"
                )
                return False
            if response.status_code != 200:
                logger.warning(
                    "Bitget API-Ping: HTTP %s (erwartet 200)", response.status_code
                )
                return False
            try:
                data = response.json()
            except Exception:
                logger.warning("Bitget API-Ping: Antwort ist kein gueltiges JSON")
                return False
            if not isinstance(data, dict) or data.get("code") != "00000":
                logger.warning(
                    "Bitget API-Key-Verifikation fehlgeschlagen: %s", data
                )
                return False
            return True
    except Exception as exc:
        logger.exception("Fehler waehrend des Bitget-API-Pings: %s", exc)
        return False


def verify_bitget_api_keys_for_tenant(tenant_id: str) -> bool:
    """
    Tenant-scoped Bitget-Ping. Fail-closed ohne aufloesbare Credentials.
    """
    if os.environ.get("APP_ENV") == "test" or os.environ.get(
        "GATEWAY_MOCK_BITGET_VERIFY"
    ) == "true":
        return _mock_verify_active()

    bundle = resolve_bitget_credentials_for_tenant(tenant_id)
    if bundle is None:
        logger.warning(
            "Bitget-Ping: keine Credentials fuer tenant_id=%s aufloesbar", tenant_id
        )
        return False
    return _ping_bitget_with_bundle(bundle)


def verify_bitget_api_keys_active() -> bool:
    """Legacy-Huelle: Ping fuer MODUL_MATE_GATE_TENANT_ID."""
    tid = (os.environ.get("MODUL_MATE_GATE_TENANT_ID") or "default").strip()
    return verify_bitget_api_keys_for_tenant(tid)
