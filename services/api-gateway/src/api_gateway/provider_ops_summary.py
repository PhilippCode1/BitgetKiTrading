"""Aggregierte Provider-Sicht fuer GET /v1/system/health (keine Secrets)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from shared_py.tenant_exchange_credentials import resolve_bitget_credentials_for_tenant

if TYPE_CHECKING:
    from api_gateway.config import GatewaySettings

_SCHEMA_VERSION = 1


def tenant_exchange_credentials_from_vault() -> bool:
    return os.environ.get(
        "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", ""
    ).strip().lower() in ("true", "1", "yes")


def _env_configured(key: str) -> bool:
    v = (os.environ.get(key) or "").strip()
    if not v:
        return False
    u = v.upper()
    if u in ("<SET_ME>", "SET_ME", "CHANGE_ME"):
        return False
    return True


def bitget_credentials_ready_for_tenant(
    tenant_id: str,
    *,
    demo: bool,
) -> tuple[bool, list[str]]:
    """
    Prueft Bitget-Zugang fuer Go-Live / Portal-Hinweise.

    Vault-Mandanten-Modus: globale BITGET_*-ENV wird ignoriert; nur
    resolve_bitget_credentials_for_tenant(tenant_id) zaehlt (fail-closed).
    """
    if demo:
        return _bitget_credentials_flags(demo=True)
    if tenant_exchange_credentials_from_vault():
        tid = (tenant_id or "").strip()
        if not tid or tid == "default":
            return False, ["bitget_tenant_vault_credentials_missing"]
        if resolve_bitget_credentials_for_tenant(tid) is None:
            return False, ["bitget_tenant_vault_credentials_missing"]
        return True, []
    return _bitget_credentials_flags(demo=False)


def bitget_env_hints_for_customer_portal(
    g: Any,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """
    Oeffentlicher Hinweis fuer Kundenkonto / Broker-Seite (keine Secret-Werte).
    """
    demo = bool(g.bitget_demo_enabled)
    tid = (tenant_id or "").strip() or None
    if demo or not tid:
        ok, gaps = _bitget_credentials_flags(demo=demo)
    else:
        ok, gaps = bitget_credentials_ready_for_tenant(tid, demo=demo)
    mode = "demo" if demo else "live"
    if ok:
        hint = (
            f"Server-ENV: Bitget-{mode}-Zugangsdaten sind vollstaendig gesetzt. "
            "Salden und Orders kommen vom Live-Broker und der Boerse — nicht von diesem Formular."
        )
    elif tenant_exchange_credentials_from_vault() and not demo:
        hint = (
            f"Bitget-{mode}: Fuer Mandant {tid or '—'} fehlen Vault-Credentials "
            f"(Pfad bitget/{{tenant_id}}/live). "
            "Ohne Mandanten-Secret gibt es keine private Bitget-Anbindung."
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
        "credentials_source": "vault_tenant" if tenant_exchange_credentials_from_vault() and not demo else "env_global",
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
