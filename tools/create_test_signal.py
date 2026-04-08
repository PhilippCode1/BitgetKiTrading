#!/usr/bin/env python3
"""
Legt ein minimales Signal + Erklaerung in Postgres an (lokaler Smoke-Test).

Voraussetzung: DATABASE_URL, Migrationen inkl. 080_signal_explanations.sql.
Aufruf vom Repo-Root:  python tools/create_test_signal.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SE_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (SE_SRC, SHARED_SRC):
    sp = str(p)
    if p.is_dir() and sp not in sys.path:
        sys.path.insert(0, sp)


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL fehlt.", file=sys.stderr)
        sys.exit(1)

    from signal_engine.config import SignalEngineSettings
    from signal_engine.explain.builder import build_explanation_bundle
    from signal_engine.explain.schemas import ExplainInput
    from signal_engine.storage.explanations_repo import ExplanationRepository
    from signal_engine.storage.repo import SignalRepository

    settings = SignalEngineSettings()
    repo = SignalRepository(settings.database_url)
    expl = ExplanationRepository(settings.database_url)

    signal_id = str(uuid4())
    analysis_ts_ms = 1_710_000_000_000
    reasons_json = {
        "structural_notes": ["demo_struct"],
        "momentum_notes": [],
        "timeframe_notes": [],
        "risk_notes": [],
    }
    row = {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "analysis_ts_ms": analysis_ts_ms,
        "market_regime": "range",
        "direction": "neutral",
        "signal_strength_0_100": 40,
        "probability_0_1": 0.45,
        "signal_class": "mikro",
        "structure_score_0_100": 40,
        "momentum_score_0_100": 40,
        "multi_timeframe_score_0_100": 40,
        "news_score_0_100": 50,
        "risk_score_0_100": 50,
        "history_score_0_100": 50,
        "weighted_composite_score_0_100": 42,
        "rejection_state": False,
        "rejection_reasons_json": [],
        "decision_state": "accepted",
        "reasons_json": reasons_json,
        "supporting_drawing_ids_json": [],
        "supporting_structure_event_ids_json": [],
        "stop_zone_id": None,
        "target_zone_ids_json": [],
        "reward_risk_ratio": None,
        "expected_volatility_band": None,
        "source_snapshot_json": {"demo": True},
        "scoring_model_version": settings.signal_scoring_model_version,
        "signal_components_history_json": [],
        "meta_decision_action": "do_not_trade",
        "meta_decision_kernel_version": None,
        "meta_decision_bundle_json": {},
        "operator_override_audit_json": None,
    }
    repo.insert_signal_v1(row)

    sig_row = dict(row)
    sig_row["stop_trigger_type"] = settings.signal_default_stop_trigger_type
    inp = ExplainInput(
        signal_row=sig_row,
        structure_state={"trend_dir": "RANGE", "compression_flag": False},
        structure_events=[],
        primary_feature={
            "trend_dir": 0,
            "rsi_14": 50.0,
            "ret_1": 0.0,
            "computed_ts_ms": analysis_ts_ms,
            "atr_14": 200.0,
        },
        features_by_tf={
            "1m": {"trend_dir": 0},
            "5m": {"trend_dir": 0},
            "15m": {"trend_dir": 0},
            "1H": {"trend_dir": 0},
            "4H": {"trend_dir": 0},
        },
        drawings=[],
        news_row=None,
        last_close=95_000.0,
    )
    bundle = build_explanation_bundle(inp, settings)
    expl.upsert_for_signal(signal_id=signal_id, bundle=bundle)
    print(signal_id)


if __name__ == "__main__":
    main()
