"""Strikte Lot-Simulation: exotische sizeMultiplier (z. B. 0.0001) liefern erwartete Ablehnung."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PAPER_BROKER_SRC = REPO_ROOT / "services" / "paper-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for p in (REPO_ROOT, PAPER_BROKER_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from paper_broker.engine.order_constraints import validate_paper_base_order_qty
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry


def _entry_lot_0001() -> BitgetInstrumentCatalogEntry:
    return BitgetInstrumentCatalogEntry(
        market_family="futures",
        symbol="SHIBUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="unit",
        metadata_verified=True,
        trading_status="normal",
        trading_enabled=True,
        subscribe_enabled=True,
        quantity_step="0.0001",
        quantity_precision=4,
        quantity_min="0.0001",
        min_notional_quote="5",
    )


def test_0_0001_lot_rejects_non_multiple_qty() -> None:
    e = _entry_lot_0001()
    with pytest.raises(ValueError, match="lot_mismatch"):
        validate_paper_base_order_qty(
            qty=Decimal("0.00015"),
            mark_or_fill_price=Decimal("1"),
            order_type="market",
            entry=e,
        )


def test_0_0001_lot_accepts_valid_steps() -> None:
    e = _entry_lot_0001()
    px = Decimal("50000")
    validate_paper_base_order_qty(
        qty=Decimal("0.0001"),
        mark_or_fill_price=px,
        order_type="market",
        entry=e,
    )
    validate_paper_base_order_qty(
        qty=Decimal("0.0002"),
        mark_or_fill_price=px,
        order_type="market",
        entry=e,
    )


def test_0_0001_lot_rejects_below_min_notional() -> None:
    e = _entry_lot_0001()
    # 0.0001 * 0.00001 = 0.00000001 USDT < 5
    with pytest.raises(ValueError, match="notional"):
        validate_paper_base_order_qty(
            qty=Decimal("0.0001"),
            mark_or_fill_price=Decimal("0.00001"),
            order_type="market",
            entry=e,
        )
