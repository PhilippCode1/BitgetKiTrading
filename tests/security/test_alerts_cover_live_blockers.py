from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROM_ALERTS = ROOT / "infra" / "observability" / "prometheus-alerts.yml"


def _alert_map() -> dict[str, dict]:
    data = yaml.safe_load(PROM_ALERTS.read_text(encoding="utf-8")) or {}
    alerts: dict[str, dict] = {}
    for group in data.get("groups") or []:
        if not isinstance(group, dict):
            continue
        for rule in group.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            name = str(rule.get("alert") or "").strip()
            if name:
                alerts[name] = rule
    return alerts


def test_required_live_blocker_alerts_exist_with_severity_and_runbook() -> None:
    alerts = _alert_map()
    required = [
        "LiveBrokerDown",
        "ApiGatewayDown",
        "MarketPipelineLag",
        "OrderbookStale",
        "MarketDataQualityFail",
        "RiskGovernorTimeout",
        "PortfolioRiskDegraded",
        "DailyLossLimitReached",
        "DrawdownLimitReached",
        "ReconcileDriftNonZero",
        "SafetyLatchActive",
        "KillSwitchActive",
        "EmergencyFlattenTriggered",
        "BitgetAuthError",
        "BitgetPermissionError",
        "BitgetApi5xxSpike",
        "RedisUnavailable",
        "PostgresUnavailable",
        "AlertEngineDown",
        "BackupRestoreFailure",
        "ShadowLiveDivergence",
    ]
    for name in required:
        assert name in alerts, f"alert missing: {name}"
        labels = alerts[name].get("labels") or {}
        ann = alerts[name].get("annotations") or {}
        assert str(labels.get("severity") or "").strip() in {"warning", "critical"}, f"missing severity: {name}"
        assert str(ann.get("runbook") or "").strip(), f"missing runbook: {name}"
