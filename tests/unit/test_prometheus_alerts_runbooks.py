"""Smoke: Alert-Regeln enthalten Runbook-Verweise (Prompt 32)."""

from __future__ import annotations

from pathlib import Path


def test_prometheus_alerts_contain_runbooks() -> None:
    root = Path(__file__).resolve().parents[2]
    p = root / "infra" / "observability" / "prometheus-alerts.yml"
    text = p.read_text(encoding="utf-8")
    alert_hits = sum(1 for line in text.splitlines() if line.lstrip().startswith("- alert:"))
    runbook_hits = sum(
        1 for line in text.splitlines() if 'runbook: "docs/monitoring_runbook.md' in line
    )
    assert alert_hits >= 8
    assert runbook_hits >= alert_hits, "Jede Regel sollte eine runbook-Annotation haben"
