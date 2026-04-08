"""Unit: Liquiditaets-/Stop-Heuristiken (Paper-Broker Risk)."""

from __future__ import annotations

from decimal import Decimal

from paper_broker.risk.liquidity import (
    escape_stop_from_liquidity,
    notional_density_peak_near,
)


def test_notional_density_finds_peak_near_candidate() -> None:
    bids = [["99900", "1"], ["99800", "0.5"]]
    asks = [["100100", "1"]]
    peak_p, peak_n = notional_density_peak_near(
        candidate=Decimal("99950"),
        side="long",
        bids_raw=bids,
        asks_raw=asks,
        scan_bps=Decimal("100"),
        entry=Decimal("100000"),
    )
    assert peak_p is not None
    assert peak_n > 0


def test_escape_stop_long_moves_down_when_cluster_too_close() -> None:
    bids_raw = [["99990", "10"]]
    asks_raw: list[list[str]] = []
    entry = Decimal("100000")
    candidate = Decimal("99995")
    new_stop, basis = escape_stop_from_liquidity(
        candidate=candidate,
        side="long",
        entry=entry,
        bids_raw=bids_raw,
        asks_raw=asks_raw,
        scan_bps=Decimal("50"),
        escape_bps=Decimal("10"),
        avoid_bps=Decimal("100"),
    )
    assert new_stop < candidate
    assert basis.get("adjusted_by_bps") == "10"
