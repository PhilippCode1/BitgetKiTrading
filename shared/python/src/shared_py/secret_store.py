"""
HashiCorp KV v2 Lesen ohne hvac-Abhaengigkeit (fail-closed, keine Logs mit Secret-Werten).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("shared_py.secret_store")


@dataclass(frozen=True)
class VaultConfig:
    addr: str
    token: str
    kv_mount: str


def vault_config_from_env() -> VaultConfig | None:
    mode = (os.environ.get("VAULT_MODE") or "").strip().lower()
    if mode not in ("hashicorp", "vault", "hc"):
        return None
    addr = (os.environ.get("VAULT_ADDR") or "").strip().rstrip("/")
    token = (os.environ.get("VAULT_TOKEN") or "").strip()
    if not addr or not token:
        return None
    mount = (os.environ.get("VAULT_KV_MOUNT") or "secret").strip().strip("/")
    return VaultConfig(addr=addr, token=token, kv_mount=mount or "secret")


def read_hashicorp_kv_v2(
    *,
    secret_path: str,
    cfg: VaultConfig | None = None,
    timeout_sec: float = 5.0,
) -> dict[str, Any] | None:
    """
    Liest KV-v2-Daten (inneres ``data``-Dict). Gibt None bei Fehler/leer zurueck.
    """
    conf = cfg or vault_config_from_env()
    if conf is None:
        return None
    path = secret_path.strip().strip("/")
    if not path:
        return None
    url = f"{conf.addr}/v1/{conf.kv_mount}/data/{path}"
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(url, headers={"X-Vault-Token": conf.token})
        if resp.status_code != 200:
            logger.warning(
                "Vault KV read failed path=%s status=%s",
                path,
                resp.status_code,
            )
            return None
        payload = resp.json()
        inner = payload.get("data", {}).get("data")
        if not isinstance(inner, dict):
            return None
        return dict(inner)
    except Exception as exc:
        logger.warning("Vault KV read error path=%s err=%s", path, exc)
        return None


def write_hashicorp_kv_v2(
    *,
    secret_path: str,
    data: dict[str, Any],
    cfg: VaultConfig | None = None,
    timeout_sec: float = 5.0,
) -> bool:
    """
    Schreibt KV-v2-Daten (inneres ``data``-Dict). Gibt False bei Fehler zurueck.
    """
    conf = cfg or vault_config_from_env()
    if conf is None:
        return False
    path = secret_path.strip().strip("/")
    if not path or not data:
        return False
    url = f"{conf.addr}/v1/{conf.kv_mount}/data/{path}"
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(
                url,
                headers={"X-Vault-Token": conf.token},
                json={"data": data},
            )
        if resp.status_code not in (200, 204):
            logger.warning(
                "Vault KV write failed path=%s status=%s",
                path,
                resp.status_code,
            )
            return False
        return True
    except Exception as exc:
        logger.warning("Vault KV write error path=%s err=%s", path, exc)
        return False


def hydrate_env_keys_from_vault(
    keys: tuple[str, ...],
    *,
    vault_path: str,
    cfg: VaultConfig | None = None,
) -> int:
    """
    Schreibt fehlende os.environ-Keys aus einem Vault-Pfad (nur wenn Key leer).
    Returns: Anzahl gesetzter Keys (ohne Werte zu loggen).
    """
    data = read_hashicorp_kv_v2(secret_path=vault_path, cfg=cfg)
    if not data:
        return 0
    applied = 0
    for key in keys:
        if (os.environ.get(key) or "").strip():
            continue
        raw = data.get(key)
        if raw is None:
            continue
        val = str(raw).strip()
        if not val:
            continue
        os.environ[key] = val
        applied += 1
    return applied
