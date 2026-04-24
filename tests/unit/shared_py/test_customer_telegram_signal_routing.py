"""Prompt 44: Signal-Telegram — High-Leverage- und Vertrags-Gating (reine Logik)."""

from __future__ import annotations

from copy import deepcopy

from shared_py.customer_telegram_notify import (
    DEFAULT_HIGH_LEVERAGE_THRESHOLD,
    signal_notification_routing_allowed,
)
from shared_py.customer_telegram_prefs import DEFAULT_PREFS


def _prefs_base() -> dict:
    d = deepcopy(DEFAULT_PREFS)
    d["notify_orders_live"] = True
    d["notify_signal_high_leverage"] = True
    d["signal_type_prefs_json"] = {}
    return d


def test_high_leverage_disabled_no_message_at_7x_others_still_ok() -> None:
    """
    Nutzer A: High-Leverage-Alerts aus -> 7x (ueber Schwellwert 5) wird blockiert.
    Nutzer B: High-Leverage an -> gleicher Trade darf (weitere Voraussetzungen vorausgesetzt).
    """
    pa = _prefs_base()
    pa["notify_signal_high_leverage"] = False
    pb = _prefs_base()
    pb["notify_signal_high_leverage"] = True
    common = {
        "category": "live_order_open",
        "trading_mode": "live",
        "leverage": 7.0,
        "high_leverage_threshold": float(DEFAULT_HIGH_LEVERAGE_THRESHOLD),
        "has_live_commercial_contract": True,
        "plan_allows_instrument_family": True,
    }
    ok_a, r_a = signal_notification_routing_allowed(pa, **common)
    ok_b, r_b = signal_notification_routing_allowed(pb, **common)
    assert ok_a is False
    assert r_a == "high_leverage_alerts_disabled"
    assert ok_b is True
    assert r_b is None


def test_4x_does_not_require_high_leverage_flag() -> None:
    p = _prefs_base()
    p["notify_signal_high_leverage"] = False
    ok, _r = signal_notification_routing_allowed(
        p,
        category="live_order",
        trading_mode="live",
        leverage=4.0,
        has_live_commercial_contract=True,
        plan_allows_instrument_family=True,
    )
    assert ok is True


def test_live_requires_contract() -> None:
    p = _prefs_base()
    ok, r = signal_notification_routing_allowed(
        p,
        category="live_order",
        trading_mode="live",
        leverage=2.0,
        has_live_commercial_contract=False,
        plan_allows_instrument_family=True,
    )
    assert ok is False
    assert r == "no_active_live_commercial_contract"


def test_signal_type_explicit_false() -> None:
    p = _prefs_base()
    p["signal_type_prefs_json"] = {"TREND_CONTINUATION": False}
    ok, r = signal_notification_routing_allowed(
        p,
        category="live_order",
        trading_mode="live",
        signal_type="TREND_CONTINUATION",
        has_live_commercial_contract=True,
        plan_allows_instrument_family=True,
    )
    assert ok is False
    assert r == "signal_type_disabled"
