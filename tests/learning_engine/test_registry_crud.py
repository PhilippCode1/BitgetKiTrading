from __future__ import annotations

import os
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from learning_engine.config import LearningEngineSettings
from learning_engine.registry import models, service, storage
from learning_engine.storage.connection import db_connect

# Benoetigt echte Postgres-Instanz (z. B. TEST_DATABASE_URL / DATABASE_URL aus docker-compose.test).
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL") and not os.environ.get("TEST_DATABASE_URL"),
        reason="DATABASE_URL oder TEST_DATABASE_URL fuer Registry-CRUD noetig",
    ),
]


def test_registry_lifecycle_promote_requires_manual_override() -> None:
    settings = LearningEngineSettings()
    bus = MagicMock()
    name = f"RegistryTest_{uuid4().hex[:10]}"
    create_body = models.CreateStrategyRequest(
        name=name,
        description="integration",
        scope=models.StrategyScope(symbol="BTCUSDT", timeframes=["5m"]),
    )
    sid: UUID | None = None
    try:
        with db_connect(settings.database_url) as conn:
            with conn.transaction():
                row = service.create_strategy(conn, settings, create_body)
                sid = row["strategy_id"]
                service.add_version(
                    conn,
                    sid,
                    models.AddVersionRequest(
                        version="1.0.0",
                        definition={"entry": "x"},
                        parameters={},
                        risk_profile={"max_leverage": 20},
                    ),
                )
                service.set_status(
                    conn,
                    bus,
                    sid,
                    models.SetStatusRequest(
                        new_status=models.StrategyLifecycleStatus.candidate,
                        reason="test",
                        changed_by="pytest",
                    ),
                )
                with pytest.raises(HTTPException) as excinfo:
                    service.set_status(
                        conn,
                        bus,
                        sid,
                        models.SetStatusRequest(
                            new_status=models.StrategyLifecycleStatus.promoted,
                            reason="should fail",
                            changed_by="pytest",
                            manual_override=False,
                        ),
                    )
                assert excinfo.value.status_code == 400

                out = service.set_status(
                    conn,
                    bus,
                    sid,
                    models.SetStatusRequest(
                        new_status=models.StrategyLifecycleStatus.promoted,
                        reason="manual promote for test",
                        changed_by="pytest",
                        manual_override=True,
                    ),
                )
                assert out["current_status"] == "promoted"
                assert out["warnings"]

        assert bus.publish.call_count == 2

        with db_connect(settings.database_url) as conn:
            promoted = storage.list_promoted_names(conn)
        assert name in promoted
    finally:
        if sid is not None:
            with db_connect(settings.database_url) as conn:
                conn.execute("DELETE FROM learn.strategies WHERE strategy_id = %s", (sid,))
