from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.uncertainty_gates import (
    binary_normalized_entropy_0_1,
    merge_meta_trade_lanes,
)


def test_merge_prefers_more_restrictive_lane() -> None:
    assert merge_meta_trade_lanes("candidate_for_live", "paper_only") == "paper_only"
    assert merge_meta_trade_lanes("paper_only", "shadow_only") == "shadow_only"
    assert merge_meta_trade_lanes(None, "candidate_for_live") == "candidate_for_live"


def test_merge_blocked_on_trade_action() -> None:
    assert (
        merge_meta_trade_lanes(
            "candidate_for_live",
            "candidate_for_live",
            trade_action_blocked=True,
        )
        == "do_not_trade"
    )


def test_entropy_max_at_half() -> None:
    assert binary_normalized_entropy_0_1(0.5) > binary_normalized_entropy_0_1(0.9)
