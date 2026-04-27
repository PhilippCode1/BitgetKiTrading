"""PATCH auf Strategieversion: 409 bei live_champion (DoD Prompt 67)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for p in (REPO_ROOT, API_GATEWAY_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")),
        reason="TEST_DATABASE_URL oder DATABASE_URL noetig",
    ),
]


def _clear_settings() -> None:
    from config.gateway_settings import get_gateway_settings

    get_gateway_settings.cache_clear()


def test_patch_strategy_version_409_for_live_champion() -> None:
    dsn = (os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    os.environ["DATABASE_URL"] = dsn
    _clear_settings()

    from config.gateway_settings import get_gateway_settings
    from shared_py.strategy_config_hash import compute_configuration_hash

    s = get_gateway_settings()
    _ = s  # resolve cache

    import psycopg
    from api_gateway.routes_registry_proxy import router
    from psycopg.rows import dict_row

    name = f"immutest_{uuid4().hex[:12]}"
    definition, parameters, risk_profile = {"k": 1}, {}, {"max_leverage": 1}
    h = compute_configuration_hash(definition, parameters, risk_profile)

    with psycopg.connect(dsn, row_factory=dict_row) as c:
        with c.transaction():
            srow = c.execute(
                """
                INSERT INTO learn.strategies (name, description, scope_json)
                VALUES (%s, %s, %s::jsonb)
                RETURNING strategy_id
                """,
                (name, "m", json.dumps({})),
            ).fetchone()
            assert srow
            sid = srow["strategy_id"]
            c.execute(
                "INSERT INTO learn.strategy_status (strategy_id, current_status) VALUES (%s, %s)",
                (str(sid), "shadow"),
            )
            v = c.execute(
                """
                INSERT INTO learn.strategy_versions
                    (strategy_id, version, definition_json, parameters_json, risk_profile_json, configuration_hash)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                RETURNING strategy_version_id
                """,
                (
                    str(sid),
                    "V1",
                    json.dumps(definition),
                    json.dumps(parameters),
                    json.dumps(risk_profile),
                    h,
                ),
            ).fetchone()
            assert v
            vid = v["strategy_version_id"]
            c.execute(
                """
                UPDATE learn.strategy_status
                SET current_status = 'live_champion', live_champion_version_id = %s, updated_ts = now()
                WHERE strategy_id = %s
                """,
                (str(vid), str(sid)),
            )

    try:
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.patch(
            f"/v1/registry/strategies/{sid}/versions/{vid}",
            json={},
        )
        assert r.status_code == 409, r.text
        d = r.json() if "application/json" in (r.headers.get("content-type") or "") else {}
        detail = d.get("detail")
        if isinstance(detail, dict):
            assert detail.get("code") == "IMMUTABLE_LIVE_CHAMPION"
    finally:
        with psycopg.connect(dsn) as c2:
            with c2.transaction():
                c2.execute("DELETE FROM learn.strategies WHERE strategy_id = %s", (str(sid),))
        _clear_settings()
