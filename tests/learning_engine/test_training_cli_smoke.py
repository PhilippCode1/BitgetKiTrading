from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


@contextmanager
def _fake_conn():
    class _C:
        def transaction(self):
            class _T:
                def __enter__(self):
                    return None

                def __exit__(self, *exc):
                    return False

            return _T()

    yield _C()


def test_training_cli_take_trade_invokes_trainer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("TAKE_TRADE_MODEL_ARTIFACTS_DIR", str(tmp_path / "tt"))

    calls: list[str] = []

    monkeypatch.setattr(
        "learning_engine.training.cli.db_connect",
        lambda _url: _fake_conn(),
    )
    monkeypatch.setattr(
        "learning_engine.training.pipeline.train_take_trade_prob_model",
        lambda *_a, **_k: calls.append("take_trade"),
    )

    from learning_engine.training.cli import main

    assert main(["take-trade"]) == 0
    assert calls == ["take_trade"]


def test_training_cli_specialists_audit_invokes_audit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("TAKE_TRADE_MODEL_ARTIFACTS_DIR", str(tmp_path / "tt"))

    calls: list[str] = []

    monkeypatch.setattr(
        "learning_engine.training.cli.db_connect",
        lambda _url: _fake_conn(),
    )
    monkeypatch.setattr(
        "learning_engine.training.pipeline.audit_specialist_training_readiness",
        lambda *_a, **_k: calls.append("audit") or {"ok": True},
    )

    from learning_engine.training.cli import main

    assert main(["specialists-audit"]) == 0
    assert calls == ["audit"]
