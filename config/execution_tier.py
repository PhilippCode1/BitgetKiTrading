"""
Abgeleitete Sicht: local / paper / exchange_sandbox / shadow / live.

Ergänzt `execution_runtime_snapshot` um `execution_tier` fuer UI und Runbooks.
"""

from __future__ import annotations

from typing import Any, Protocol

EXECUTION_TIER_SCHEMA_VERSION = 1


class ExecutionTierSettingsView(Protocol):
    """Minimale Schnittstelle (kein Zwang zu BitgetSettings)."""

    app_env: str
    production: bool
    execution_mode: str
    strategy_execution_mode: str
    bitget_demo_enabled: bool
    live_broker_enabled: bool
    live_trade_enable: bool
    shadow_trade_enable: bool

    @property
    def paper_path_active(self) -> bool: ...

    @property
    def shadow_path_active(self) -> bool: ...

    @property
    def live_order_submission_enabled(self) -> bool: ...


def build_execution_tier_payload(s: ExecutionTierSettingsView) -> dict[str, Any]:
    """Kanonischer Block unter `execution_runtime.execution_tier`."""
    demo = bool(s.bitget_demo_enabled)
    mode = str(s.execution_mode)
    strategy_auto = s.strategy_execution_mode == "auto"
    live_submit = bool(s.live_order_submission_enabled)
    automated_live = live_submit and strategy_auto

    if demo:
        trading_plane = "exchange_sandbox"
    elif mode == "paper":
        trading_plane = "paper"
    elif mode == "shadow":
        trading_plane = "shadow"
    elif mode == "live":
        trading_plane = "live"
    else:
        trading_plane = "paper"

    if s.production:
        deployment = "production"
    elif s.app_env == "local":
        deployment = "local"
    elif s.app_env in ("development", "test"):
        deployment = "development"
    else:
        deployment = "non_production"

    return {
        "schema_version": EXECUTION_TIER_SCHEMA_VERSION,
        "deployment": deployment,
        "app_env": s.app_env,
        "production": s.production,
        "trading_plane": trading_plane,
        "execution_mode": mode,
        "bitget_demo_enabled": demo,
        "live_broker_enabled": s.live_broker_enabled,
        "live_order_submission_enabled": live_submit,
        "automated_live_orders_enabled": automated_live,
        "strategy_execution_mode": s.strategy_execution_mode,
        "implicit_mode_switch_risk": (
            "EXECUTION_MODE und BITGET_DEMO_ENABLED sind nur per Deploy/ENV aenderbar; "
            "kein stiller Laufzeitwechsel in Live."
        ),
    }
