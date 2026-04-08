from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

SERVICE_SRC = (
    Path(__file__).resolve().parents[2] / "services" / "drawing-engine" / "src"
)
if SERVICE_SRC.is_dir() and str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))

from drawing_engine.algorithms.zones import (
    cluster_sorted_prices,
    confidence_from_touch_count,
    zone_from_cluster,
)


def test_cluster_merges_close_prices() -> None:
    prices = [
        Decimal("100"),
        Decimal("100.02"),
        Decimal("100.015"),
        Decimal("101.5"),
    ]
    clusters = cluster_sorted_prices(prices, cluster_bps=Decimal("30"))
    assert len(clusters) == 2
    assert len(clusters[0]) == 3
    assert clusters[1] == [Decimal("101.5")]


def test_zone_padding() -> None:
    zl, zh = zone_from_cluster(
        [Decimal("100"), Decimal("100.01")],
        pad_bps=Decimal("10"),
    )
    assert zl < Decimal("100")
    assert zh > Decimal("100.01")


def test_confidence_cap() -> None:
    assert confidence_from_touch_count(10) == 100
    assert confidence_from_touch_count(1) == 35
