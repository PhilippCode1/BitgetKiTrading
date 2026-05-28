"""
Mandanten-ID fuer Modul-Mate-Gates: Order-/Intent-Kontext vor Container-Default.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_TENANT_ID_RE = re.compile(r"^[a-z0-9_-]{3,64}$", re.IGNORECASE)


def _tenant_from_mapping(src: Mapping[str, Any] | None) -> str | None:
    if src is None:
        return None
    raw = src.get("tenant_id")
    if not isinstance(raw, str):
        return None
    tid = raw.strip()
    if not tid or tid == "default":
        return None
    if not _TENANT_ID_RE.fullmatch(tid):
        return None
    return tid


def resolve_modul_mate_gate_tenant_id(
    *,
    config_tenant_id: str,
    trace: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> str:
    """
    Bevorzugt tenant_id aus Intent/Order-Trace oder Payload; sonst Container-Config.
    """
    for src in (trace, payload):
        tid = _tenant_from_mapping(src)
        if tid:
            return tid
    fallback = (config_tenant_id or "default").strip() or "default"
    return fallback
