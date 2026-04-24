"""
DoD P79: Trigger simuliert, strukturierter Post-Mortem-Insert unter 10s
(LLM+Telegram gemaockt, lokale I/O-bezogene Pfad).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import Response

from monitor_engine.incident_rca.post_mortem import run_incident_post_mortem_once
from shared_py.eventbus import RedisStreamBus


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "postgresql://localhost:5432/postgres"
    s.monitor_incident_rca_global_budget_sec = 8.0
    s.monitor_llm_orchestrator_url = "http://localhost:8070"
    s.monitor_alert_engine_url = "http://localhost:8100"
    s.monitor_telegram_post_mortem_enabled = False
    s.service_internal_api_key = "test-internal"
    s.production = False
    s.service_urls = {"test-svc": "http://127.0.0.1:1"}
    return s


def test_post_mortem_completes_under_10s_with_mocks() -> None:
    async def _run() -> str:
        settings = _make_settings()
        bus = MagicMock(spec=RedisStreamBus)
        bus.redis = MagicMock()
        bus.redis.get = MagicMock(return_value="0")
        t0 = time.perf_counter()

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "incident_summary_de": "Kurztest: Fake-Auslöser.",
                        "root_causes_de": ["A"],
                    },
                },
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        h_async = MagicMock(return_value=mock_client)

        with (
            patch(
                "monitor_engine.incident_rca.post_mortem"
                ".sample_event_streams_union_recent",
                return_value=[
                    {
                        "stream": "events:system_alert",
                        "message_id": "1-0",
                        "x": 1,
                    }
                ],
            ),
            patch(
                "monitor_engine.incident_rca.post_mortem.collect_service_ready_snapshot",
                new_callable=AsyncMock,
                return_value=[{"service": "api-gateway", "http_status": 200, "status": "ok"}],
            ),
            patch("monitor_engine.incident_rca.post_mortem.httpx.AsyncClient", h_async),
            patch("monitor_engine.incident_rca.post_mortem.insert_post_mortem") as ins,
        ):
            pm = await run_incident_post_mortem_once(
                settings,
                bus,  # type: ignore[arg-type]
                time_budget_sec=8.0,
            )
        elapsed = time.perf_counter() - t0
        assert ins.called, "muss in DB speichern"
        assert elapsed < 10.0, f"erwartet <10s, war {elapsed:.2f}s"
        return str(pm)

    out = asyncio.run(_run())
    assert len(out) == 36
    uuid.UUID(out)
