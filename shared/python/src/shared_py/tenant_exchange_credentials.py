"""
Bitget-Credentials pro Mandant: Vault-Pfad-Konvention + Single-Tenant-ENV-Fallback.

Multi-Tenant-Live erfordert TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true und
Runtime-Hydration aus dem Secret Store (Pfad: bitget/{tenant_id}/live).
Ohne Vault bleibt ein globales ENV-Tripel fuer den aktiven Gate-Tenant erlaubt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from shared_py.bitget import BitgetSettings
from shared_py.secret_store import read_hashicorp_kv_v2, vault_config_from_env


@dataclass(frozen=True)
class BitgetCredentialBundle:
    api_key: str
    api_secret: str
    api_passphrase: str
    source: str  # env_global | vault_tenant


def vault_secret_path_for_tenant(tenant_id: str) -> str:
    tid = (tenant_id or "").strip().lower()
    return f"bitget/{tid}/live"


def _bundle_from_mapping(data: dict[str, str | object], *, source: str) -> BitgetCredentialBundle | None:
    key = str(data.get("api_key") or data.get("BITGET_API_KEY") or "").strip()
    secret = str(data.get("api_secret") or data.get("BITGET_API_SECRET") or "").strip()
    phrase = str(
        data.get("api_passphrase") or data.get("BITGET_API_PASSPHRASE") or ""
    ).strip()
    if not key or not secret or not phrase:
        return None
    return BitgetCredentialBundle(
        api_key=key,
        api_secret=secret,
        api_passphrase=phrase,
        source=source,
    )


def _credentials_from_vault(tenant_id: str) -> BitgetCredentialBundle | None:
    cfg = vault_config_from_env()
    if cfg is None:
        return None
    path = vault_secret_path_for_tenant(tenant_id)
    data = read_hashicorp_kv_v2(secret_path=path, cfg=cfg)
    if not data:
        return None
    return _bundle_from_mapping(data, source="vault_tenant")


def resolve_bitget_credentials_for_tenant(tenant_id: str) -> BitgetCredentialBundle | None:
    """
    Liefert Credentials fuer Go-Live-Ping und Live-Broker-Submit.

    Fail-closed: unbekannter Mandant ohne Vault-Hydration -> None.
    """
    tid = (tenant_id or "").strip()
    if not tid or tid == "default":
        return None

    from_vault = os.environ.get(
        "TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", ""
    ).strip().lower() in ("true", "1", "yes")
    vault_mode = (os.environ.get("VAULT_MODE") or "").strip().lower()

    if from_vault and vault_mode in ("hashicorp", "aws"):
        bundle = _credentials_from_vault(tid)
        if bundle is not None:
            return bundle
        return None

    config_tid = (os.environ.get("MODUL_MATE_GATE_TENANT_ID") or "default").strip()
    multi = os.environ.get("TENANT_EXCHANGE_CREDENTIALS_MULTI", "").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    if multi:
        return None

    if config_tid not in ("", "default") and tid != config_tid:
        return None

    return _credentials_from_env()


def _credentials_from_env() -> BitgetCredentialBundle | None:
    settings = BitgetSettings()
    key = (settings.api_key or "").strip()
    secret = (settings.api_secret or "").strip()
    phrase = (settings.api_passphrase or "").strip()
    if not key or not secret or not phrase:
        return None
    return BitgetCredentialBundle(
        api_key=key,
        api_secret=secret,
        api_passphrase=phrase,
        source="env_global",
    )
