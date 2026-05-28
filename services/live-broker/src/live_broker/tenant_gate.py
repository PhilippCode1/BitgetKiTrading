"""Live-Broker: Mandanten-Kontext fuer kommerzielle Gates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared_py.tenant_gate_context import resolve_modul_mate_gate_tenant_id


def gate_tenant_from_intent(
    *,
    config_tenant_id: str,
    trace: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> str:
    return resolve_modul_mate_gate_tenant_id(
        config_tenant_id=config_tenant_id,
        trace=trace,
        payload=payload,
    )
