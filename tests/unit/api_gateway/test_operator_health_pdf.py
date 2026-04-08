from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"

for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

pytest.importorskip("fpdf", reason="fpdf2-Paket (Modul fpdf) fuer PDF-Tests")

from api_gateway.operator_health_pdf import build_operator_health_pdf  # noqa: E402


def test_build_operator_health_pdf_smoke() -> None:
    health = {
        "symbol": "BTCUSDT",
        "database": "ok",
        "redis": "ok",
        "warnings": ["monitor_alerts_open"],
        "warnings_display": [
            {
                "code": "monitor_alerts_open",
                "title": "Test",
                "message": "Msg",
                "next_step": "Fix",
                "related_services": "monitor-engine",
                "machine": {"problem_id": "test", "verify_commands": []},
            }
        ],
        "execution": {"execution_mode": "paper"},
        "data_freshness": {},
        "ops": {"monitor": {"open_alert_count": 1}},
        "services": [{"name": "api-gateway", "status": "ok", "configured": True}],
        "integrations_matrix": None,
    }
    raw = build_operator_health_pdf(
        health=health,
        open_alerts=[],
        outbox_rows=[],
        generated_at_iso="2026-03-31T12:00:00+00:00",
    )
    assert raw[:4] == b"%PDF"
    assert len(raw) > 2000
