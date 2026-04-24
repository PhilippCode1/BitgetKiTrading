"""Prompt 49: Konsens-Penalty aus War-Room / Apex + Dataset-Builder-Spalte."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from learning_engine.consensus import tsfm_learning_feedback as tlf
from learning_engine.consensus.tsfm_learning_feedback import (
    consensus_to_labels,
    enrich_trade_evaluations_with_apex_war_room,
    specialist_disagreement_from_war_room,
)
from shared_py.training_dataset_builder import (  # noqa: E402
    TakeTradeDatasetBuildConfig,
    _example_from_evaluation_row,
    build_take_trade_training_dataset,
)


def test_specialist_disagreement() -> None:
    assert specialist_disagreement_from_war_room(
        {"macro_quant_high_uncertainty": True, "consensus_status": "ok"},
    )
    assert specialist_disagreement_from_war_room({"consensus_status": "high_uncertainty"})


def test_consensus_to_labels_hard_lesson() -> None:
    wr = {
        "macro_quant_high_uncertainty": True,
        "consensus_status": "high_uncertainty",
    }
    cp, uw = consensus_to_labels(
        wr,
        pnl_net_usdt=-10.0,
        has_signal_link=True,
    )
    assert cp == 1.0
    assert uw == 3.0
    cp2, uw2 = consensus_to_labels(wr, pnl_net_usdt=1.0, has_signal_link=True)
    assert cp2 == 0.25
    assert uw2 == 1.25
    assert consensus_to_labels(wr, pnl_net_usdt=-1.0, has_signal_link=False) == (0.0, 1.0)


def test_enrich_with_stubbed_apex() -> None:
    sid = uuid4()
    orig = tlf._fetch_by_signal_json_path

    def _stub(
        _conn: object, signal_id_strs: list[str]
    ) -> list[dict]:
        assert str(sid) in signal_id_strs
        pld = {
            "market_event_json": {"signal_id": str(sid)},
            "war_room": {
                "consensus_status": "high_uncertainty",
                "macro_quant_high_uncertainty": True,
            },
        }
        return [
            {
                "id": 1,
                "decision_id": str(uuid4()),
                "created_at": "2020-01-01",
                "canonical_payload_text": json.dumps(
                    pld, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
            }
        ]

    tlf._fetch_by_signal_json_path = _stub  # type: ignore[assignment]
    try:
        rows: list[dict] = [
            {
                "paper_trade_id": uuid4(),
                "decision_ts_ms": 0,
                "closed_ts_ms": 1,
                "take_trade_label": True,
                "pnl_net_usdt": -5.0,
                "signal_id": str(sid),
            }
        ]
        out = enrich_trade_evaluations_with_apex_war_room(None, rows)  # type: ignore[arg-type]
        assert out[0]["consensus_penalty"] == 1.0
        assert out[0]["uncertainty_weight"] == 3.0
    finally:
        tlf._fetch_by_signal_json_path = orig  # type: ignore[assignment]


def test_dataset_example_contains_consensus_columns() -> None:
    ex = _example_from_evaluation_row(
        {
            "paper_trade_id": "x",
            "decision_ts_ms": 0,
            "closed_ts_ms": 1,
            "take_trade_label": True,
            "consensus_penalty": 0.5,
            "uncertainty_weight": 2.0,
        }
    )
    assert ex is not None
    assert ex.get("consensus_penalty") == 0.5
    assert ex.get("uncertainty_weight") == 2.0


def test_dod_build_includes_consensus_in_kept_examples() -> None:
    from tests.shared.test_training_dataset_builder import (  # noqa: PLC0415
        _good_row,
    )

    row = _good_row()  # type: ignore[assignment]
    row = dict(row)
    row["consensus_penalty"] = 0.8
    row["uncertainty_weight"] = 2.5
    ex, _rep = build_take_trade_training_dataset(
        [row], TakeTradeDatasetBuildConfig()
    )
    assert len(ex) == 1
    assert ex[0].get("consensus_penalty") == 0.8
    assert ex[0].get("uncertainty_weight") == 2.5
