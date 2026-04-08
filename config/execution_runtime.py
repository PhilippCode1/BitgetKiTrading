"""
Gemeinsames Ausfuehrungsmodell (paper / shadow / live).

Alle Services und das Dashboard sollen dieselbe semantische Sicht nutzen
(`execution_runtime_snapshot`), abgeleitet aus den zentralen ENV-Flags in
`BaseServiceSettings`.
"""

from __future__ import annotations

from typing import Any, Protocol

from config.execution_tier import build_execution_tier_payload

EXECUTION_RUNTIME_SCHEMA_VERSION = 2


class ExecutionRuntimeSettingsView(Protocol):
    """Minimale Schnittstelle fuer Snapshot-Berechnung (vermeidet Zyklen)."""

    execution_mode: str
    strategy_execution_mode: str
    live_broker_enabled: bool
    shadow_trade_enable: bool
    live_trade_enable: bool

    @property
    def paper_path_active(self) -> bool: ...

    @property
    def shadow_path_active(self) -> bool: ...

    @property
    def live_order_submission_enabled(self) -> bool: ...

    @property
    def private_exchange_access_enabled(self) -> bool: ...


def build_execution_runtime_snapshot(s: ExecutionRuntimeSettingsView) -> dict[str, Any]:
    """Kanonisches JSON/Dict fuer Health, Gateway, Dashboard, Runbooks."""
    config_live_orders = bool(s.live_order_submission_enabled)
    strategy_auto = s.strategy_execution_mode == "auto"
    automated_exchange_orders = config_live_orders and strategy_auto

    snapshot = {
        "schema_version": EXECUTION_RUNTIME_SCHEMA_VERSION,
        "primary_mode": s.execution_mode,
        "strategy_execution_mode": s.strategy_execution_mode,
        "flags": {
            "live_broker_enabled": s.live_broker_enabled,
            "shadow_trade_enable": s.shadow_trade_enable,
            "live_trade_enable": s.live_trade_enable,
        },
        "paths": {
            "paper_path_active": s.paper_path_active,
            "shadow_path_active": s.shadow_path_active,
            "live_order_submission_enabled": s.live_order_submission_enabled,
            "private_exchange_access_enabled": s.private_exchange_access_enabled,
        },
        "capabilities": {
            "live_broker_consumes_signals": not s.paper_path_active,
            "shadow_decision_journal": s.shadow_path_active,
            "exchange_private_data_plane": s.private_exchange_access_enabled,
            "exchange_order_submit_env_ok": config_live_orders,
            "exchange_order_submit_automated": automated_exchange_orders,
            "paper_is_primary_execution_plane": s.paper_path_active,
        },
        "live_release": {
            "env_allows_live_orders": config_live_orders,
            "strategy_auto_required_for_automated_exchange_orders": True,
            "fully_released_for_automated_exchange_orders": automated_exchange_orders,
            "manual_strategy_holds_live_firewall": (
                config_live_orders and not strategy_auto
            ),
        },
        "execution_tier": build_execution_tier_payload(s),
    }
    config_snapshot = getattr(s, "configuration_runtime_snapshot", None)
    if callable(config_snapshot):
        snapshot["configuration"] = config_snapshot()
    return snapshot
