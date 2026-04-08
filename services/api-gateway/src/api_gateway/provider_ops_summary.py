"""Aggregierte Provider-Sicht fuer GET /v1/system/health (keine Secrets)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_gateway.config import GatewaySettings

_SCHEMA_VERSION = 1


def _env_configured(key: str) -> bool:
    v = (os.environ.get(key) or "").strip()
    if not v:
        return False
    u = v.upper()
    if u in ("<SET_ME>", "SET_ME", "CHANGE_ME"):
        return False
    return True


def bitget_env_hints_for_customer_portal(g: Any) -> dict[str, Any]:
    """
    Oeffentlicher Hinweis fuer Kundenkonto / Broker-Seite (keine Secret-Werte).
    """
    demo = bool(g.bitget_demo_enabled)
    ok, gaps = _bitget_credentials_flags(demo=demo)
    mode = "demo" if demo else "live"
    if ok:
        hint = (
            f"Server-ENV: Bitget-{mode}-Zugangsdaten sind vollstaendig gesetzt. "
            "Salden und Orders kommen vom Live-Broker und der Boerse — nicht von diesem Formular."
        )
    else:
        keys = (
            "BITGET_DEMO_API_KEY, BITGET_DEMO_API_SECRET, BITGET_DEMO_API_PASSPHRASE"
            if demo
            else "BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE"
        )
        hint = (
            f"Bitget-{mode}: In der Gateway-Umgebung fehlen Pflichtfelder ({keys}). "
            "Ohne vollstaendiges Tripel gibt es keine private Bitget-Anbindung."
        )
    return {
        "exchange_mode": mode,
        "credentials_complete": ok,
        "gap_codes": gaps,
        "hint_public_de": hint,
    }


def _bitget_credentials_flags(*, demo: bool) -> tuple[bool, list[str]]:
    gaps: list[str] = []
    if demo:
        ok = all(
            _env_configured(k)
            for k in (
                "BITGET_DEMO_API_KEY",
                "BITGET_DEMO_API_SECRET",
                "BITGET_DEMO_API_PASSPHRASE",
            )
        )
        if not ok:
            gaps.append("bitget_demo_credentials_incomplete")
        return ok, gaps
    ok = all(
        _env_configured(k)
        for k in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE")
    )
    if not ok:
        gaps.append("bitget_live_credentials_incomplete")
    return ok, gaps


def _llm_openai_configured() -> bool:
    return _env_configured("OPENAI_API_KEY")


def _service_by_name(
    services: list[dict[str, Any]],
    name: str,
) -> dict[str, Any] | None:
    for s in services:
        if s.get("name") == name:
            return s
    return None


def build_provider_ops_summary(
    g: GatewaySettings,
    services: list[dict[str, Any]],
) -> dict[str, Any]:
    demo = bool(g.bitget_demo_enabled)
    bitget_ok, bitget_gaps = _bitget_credentials_flags(demo=demo)
    openai_e = _llm_openai_configured()
    fake_llm = bool(g.llm_use_fake_provider)

    exchange_mode = "demo" if demo else "live"
    trading_plane = "exchange_sandbox" if demo else "live"

    hint_codes = list(bitget_gaps)

    ms = _service_by_name(services, "market-stream")
    ms_http = None
    if ms and isinstance(ms.get("http_status"), int):
        ms_http = int(ms["http_status"])
    ms_st = str(ms.get("status", "")).strip().lower() if ms else ""
    if ms_http == 429:
        hint_codes.append("market_stream_http_429")
    elif ms and ms_st in {"error", "degraded"} and ms.get("configured"):
        hint_codes.append("market_stream_probe_degraded")

    orch = _service_by_name(services, "llm-orchestrator")
    orch_slice: dict[str, Any] = {}
    if orch and orch.get("configured"):
        for k in (
            "status",
            "http_status",
            "redis_ok",
            "fake_mode",
            "openai_configured",
            "any_provider_configured",
            "llm_provider_gap",
        ):
            if k in orch:
                orch_slice[k] = orch[k]
        oa = orch.get("openai")
        if isinstance(oa, dict):
            st = oa.get("structured_transport")
            if st is not None:
                orch_slice["openai_structured_transport"] = st
        if orch_slice.get("llm_provider_gap") is True:
            hint_codes.append("llm_orchestrator_no_provider")
        if int(orch.get("http_status") or 0) == 429:
            hint_codes.append("llm_orchestrator_http_429")
    elif not fake_llm and not openai_e:
        hint_codes.append("llm_env_keys_missing")

    hint_codes = list(dict.fromkeys(hint_codes))

    return {
        "schema_version": _SCHEMA_VERSION,
        "bitget": {
            "exchange_mode": exchange_mode,
            "trading_plane_hint": trading_plane,
            "bitget_demo_enabled": demo,
            "credentials_complete": bitget_ok,
            "gap_codes": bitget_gaps,
        },
        "llm": {
            "llm_use_fake_provider": fake_llm,
            "openai_key_present_gateway_env": openai_e,
            "orchestrator_probe": orch_slice or None,
        },
        "hint_codes": hint_codes,
    }
