from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIG_SRC = ROOT / "services" / "signal-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (SIG_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME
from signal_engine.storage.repo import SignalRepository


@pytest.fixture
def fake_psycopg_connect(monkeypatch: pytest.MonkeyPatch):
    last_sql: dict[str, str] = {}

    class FakeCursor:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class FakeConn:
        def __init__(self, row):
            self._row = row

        def execute(self, sql, params=None):
            last_sql["sql"] = sql
            return FakeCursor(self._row)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def factory(url, **kwargs):
        return FakeConn(factory.row)

    factory.row = None
    factory.last_sql = last_sql
    monkeypatch.setattr("signal_engine.storage.repo.psycopg.connect", factory)
    return factory


def test_fetch_production_joins_registry_when_enabled(fake_psycopg_connect) -> None:
    fake_psycopg_connect.row = {
        "run_id": UUID(int=1),
        "model_name": TAKE_TRADE_MODEL_NAME,
        "version": "v1",
        "dataset_hash": "h",
        "metrics_json": {},
        "promoted_bool": True,
        "artifact_path": "artifacts/x",
        "target_name": "take_trade_label",
        "output_field": "take_trade_prob",
        "calibration_method": "sigmoid",
        "metadata_json": {},
        "created_ts": None,
        "registry_role": "champion",
        "registry_calibration_status": "verified",
        "registry_activated_ts": None,
        "registry_scope_type": "global",
        "registry_scope_key": "",
    }
    repo = SignalRepository(
        "postgresql://x",
        model_registry_v2_enabled=True,
        model_calibration_required=False,
        model_champion_name=TAKE_TRADE_MODEL_NAME,
    )
    row = repo.fetch_production_model_run(model_name=TAKE_TRADE_MODEL_NAME)
    assert row is not None
    assert "model_registry_v2" in fake_psycopg_connect.last_sql["sql"]
    assert "g.scope_type" in fake_psycopg_connect.last_sql["sql"]


def test_fetch_production_blocked_when_calibration_required(
    fake_psycopg_connect,
) -> None:
    fake_psycopg_connect.row = {
        "run_id": UUID(int=2),
        "model_name": TAKE_TRADE_MODEL_NAME,
        "version": "v1",
        "dataset_hash": "h",
        "metrics_json": {},
        "promoted_bool": True,
        "artifact_path": "artifacts/x",
        "target_name": None,
        "output_field": None,
        "calibration_method": None,
        "metadata_json": {},
        "created_ts": None,
        "registry_role": "champion",
        "registry_calibration_status": "missing",
        "registry_activated_ts": None,
    }
    repo = SignalRepository(
        "postgresql://x",
        model_registry_v2_enabled=True,
        model_calibration_required=True,
        model_champion_name=TAKE_TRADE_MODEL_NAME,
    )
    assert repo.fetch_production_model_run(model_name=TAKE_TRADE_MODEL_NAME) is None


def test_fetch_production_legacy_promoted_when_registry_disabled(
    fake_psycopg_connect,
) -> None:
    fake_psycopg_connect.row = {
        "run_id": UUID(int=3),
        "model_name": "expected_return_bps",
        "version": "v1",
        "dataset_hash": "h",
        "metrics_json": {},
        "promoted_bool": True,
        "artifact_path": "artifacts/y",
        "target_name": None,
        "output_field": None,
        "calibration_method": None,
        "metadata_json": {},
        "created_ts": None,
        "registry_role": None,
        "registry_calibration_status": None,
        "registry_activated_ts": None,
        "registry_scope_type": None,
        "registry_scope_key": None,
    }
    repo = SignalRepository(
        "postgresql://x",
        model_registry_v2_enabled=False,
        model_calibration_required=False,
    )
    row = repo.fetch_production_model_run(model_name="expected_return_bps")
    assert row is not None
    assert "promoted_bool = true" in fake_psycopg_connect.last_sql["sql"]
