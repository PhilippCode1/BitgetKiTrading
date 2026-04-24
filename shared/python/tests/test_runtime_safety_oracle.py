"""
P75: Runtime-Safety-Oracle — Axiome und Kill-Chain (ohne echten DB-Layer).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from shared_py.bitget.runtime_safety_oracle import (
    RuntimeSafetyConfig,
    RuntimeSafetyOracle,
    check_axiom_notional_equity_breach,
)


def test_axiom_notional_exceeds_equity_multiple() -> None:
    positions = [
        {
            "notional_value": Decimal("1000000"),
        }
    ]
    ax = check_axiom_notional_equity_breach(
        positions,
        equity=Decimal("100"),
        max_mult=Decimal("10"),
    )
    assert ax is not None
    assert ax.id == "AXIOM_NOTIONAL_EQUITY_BREACH"


def test_maybe_emit_publishes_halt_and_latch() -> None:
    cfg = RuntimeSafetyConfig(telegram_dedupe_sec=0.0)
    o = RuntimeSafetyOracle(config=cfg)
    v = check_axiom_notional_equity_breach(
        [{"notional_value": "5000"}],
        equity=Decimal("100"),
        max_mult=Decimal("10"),
    )
    assert v is not None
    pub = MagicMock()
    latch = MagicMock()
    bus = object()
    o.maybe_emit_side_effects(
        [v],
        now=1.0,
        redis_url="",
        publish_halt=pub,
        force_latch=latch,
        publish_system_alert=MagicMock(),
        publish_operator_intel=MagicMock(),
        bus=bus,
    )
    pub.assert_called_once_with(True)
    latch.assert_called_once_with("runtime_safety_oracle:AXIOM_NOTIONAL_EQUITY_BREACH")
    o.maybe_emit_side_effects(
        [v],
        now=2.0,
        redis_url="",
        publish_halt=pub,
        force_latch=latch,
    )
    assert pub.call_count == 1, "Deduplication: Halt einmalig pro Axiom-Fingerprint"
    assert latch.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
