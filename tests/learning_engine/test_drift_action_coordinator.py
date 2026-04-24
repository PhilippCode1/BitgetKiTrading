from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg
import pytest

from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


def test_coordinator_logs_and_skips_retrain_on_handler(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:5432/t")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("TAKE_TRADE_MODEL_ARTIFACTS_DIR", str(tmp_path / "tt"))
    from learning_engine.config import LearningEngineSettings
    from learning_engine.drift.adwin_detector import MseAdwinDriftMonitor
    from learning_engine.drift.drift_action_coordinator import DriftActionCoordinator

    s = LearningEngineSettings()
    s.learning_drift_skip_event_bus = True
    s.learning_drift_retrain_cooldown_sec = 0
    mon = MseAdwinDriftMonitor(delta=0.5, min_window=8, max_window=100, min_confidence=0.5)
    fired: list[str] = []

    def _h() -> None:
        fired.append("ok")

    c = DriftActionCoordinator(
        s,
        monitor=mon,
        retrain_handler=_h,
    )
    first = [0.01] * 12
    second = [1.0] * 20
    caplog.set_level(logging.WARNING)
    for m in first + second:
        c.on_mse(m)
    assert any("AUTO_RETRAIN_TRIGGERED" in r.message for r in caplog.records)
    assert fired == ["ok"]


@pytest.mark.integration
def test_coordinator_smoke_inprocess_creates_pending_eval(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dsn = os.getenv("TEST_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL nicht gesetzt")
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("REDIS_URL", os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/0"))
    monkeypatch.setenv("TAKE_TRADE_MODEL_ARTIFACTS_DIR", str(tmp_path / "tt"))
    from learning_engine.config import LearningEngineSettings
    from learning_engine.drift.adwin_detector import MseAdwinDriftMonitor
    from learning_engine.drift.drift_action_coordinator import DriftActionCoordinator

    s = LearningEngineSettings()
    s.learning_drift_skip_event_bus = True
    s.learning_drift_retrain_cooldown_sec = 0
    s.learning_drift_retrain_inprocess = True
    s.learning_drift_retrain_smoke = True
    mon = MseAdwinDriftMonitor(delta=0.5, min_window=8, max_window=100, min_confidence=0.5)
    c = DriftActionCoordinator(s, monitor=mon)
    caplog.set_level(logging.WARNING)
    for m in [0.01] * 12 + [1.0] * 20:
        c.on_mse(m)
    assert any("AUTO_RETRAIN_TRIGGERED" in r.message for r in caplog.records)

    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            """
            SELECT run_id, metadata_json::text, calibration_status
            FROM app.model_runs r
            JOIN app.model_registry_v2 g
              ON g.run_id = r.run_id AND g.model_name = r.model_name
            WHERE r.model_name = %s AND g.role = 'challenger' AND g.calibration_status = 'PENDING_EVAL'
              AND r.version = 'drift-smoke' AND (r.metadata_json->>'origin') = 'drift_mse_retrain_smoke'
            ORDER BY r.created_ts DESC
            LIMIT 1
            """,
            (TAKE_TRADE_MODEL_NAME,),
        ).fetchone()
    assert row is not None, "Erwartet PENDING_EVAL Challenger-Stub nach Drift-Smoke-Retrain"
    run_id = row[0]
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "DELETE FROM app.model_registry_v2 WHERE run_id = %s AND model_name = %s",
            (str(run_id), TAKE_TRADE_MODEL_NAME),
        )
        conn.execute("DELETE FROM app.model_runs WHERE run_id = %s", (str(run_id),))
        conn.commit()
