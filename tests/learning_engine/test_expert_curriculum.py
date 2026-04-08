from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
if LEARNING_SRC.is_dir() and str(LEARNING_SRC) not in sys.path:
    sys.path.insert(0, str(LEARNING_SRC))

from learning_engine.curriculum.expert_curriculum import (  # noqa: E402
    build_expert_curriculum_overlay,
    cluster_expert_key,
)
from learning_engine.config import LearningEngineSettings  # noqa: E402


def test_cluster_expert_key_normalizes() -> None:
    assert cluster_expert_key(market_family="Futures", market_regime="Trend") == "futures::trend"


def test_curriculum_overlay_merges_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    s = LearningEngineSettings()
    report = {
        "symbol_audit": [{"symbol": "X", "n_after_gates": 10, "degrade_to_cluster_expert": True}],
        "family_audit": [],
        "cluster_audit": [],
        "regime_audit": [],
        "playbook_audit": [],
        "families_below_min_rows": [],
    }
    overlay = build_expert_curriculum_overlay(report, s)
    assert overlay["curriculum_version"]
    assert overlay["degrade_summary"]["symbols_below_min_rows"]
