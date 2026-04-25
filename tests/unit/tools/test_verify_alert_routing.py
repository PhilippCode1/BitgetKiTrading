from __future__ import annotations

import importlib.util
import textwrap
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "tools" / "verify_alert_routing.py"


def _load():
    n = f"var_{uuid.uuid4().hex[:8]}"
    s = importlib.util.spec_from_file_location(n, TOOL)
    m = importlib.util.module_from_spec(s)
    assert s and s.loader
    s.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def _write(p: Path, content: str) -> Path:
    p.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return p


def _alerts_minimal(p: Path) -> Path:
    return _write(
        p,
        """
        groups:
          - name: core
            rules:
              - alert: GatewayHighErrorRate
                labels: {severity: critical, alert_tier: p0}
                annotations: {runbook: "docs/monitoring_runbook.md#p0-slo-und-wiring"}
              - alert: LiveBrokerDown
                labels: {severity: critical, alert_tier: p0}
                annotations: {runbook: "docs/monitoring_runbook.md#reconcile-lag"}
              - alert: KillSwitchActive
                labels: {severity: critical}
                annotations: {runbook: "docs/monitoring_runbook.md#kill-switch-active"}
              - alert: MarketPipelineLag
                labels: {severity: critical, alert_tier: p0}
                annotations: {runbook: "docs/monitoring_runbook.md#data-stale-candles"}
              - alert: ReconcileLagHigh
                labels: {severity: critical}
                annotations: {runbook: "docs/monitoring_runbook.md#reconcile-lag"}
              - alert: LlmHighErrorRate
                labels: {severity: warning}
                annotations: {runbook: "docs/monitoring_runbook.md#llm-dlq"}
              - alert: GatewayAuthAnomalies
                labels: {severity: warning}
                annotations: {runbook: "docs/monitoring_runbook.md#auth-anomalies"}
        """,
    )


def test_pass_example_config(tmp_path: Path) -> None:
    m = _load()
    p = REPO / "infra" / "observability" / "alertmanager.yml.example"
    af = REPO / "infra" / "observability" / "prometheus-alerts.yml"
    st, issues, _meta = m.verify(p, True, {"PATH": "x"}, af)
    assert st == "PASS", issues
    assert not issues


def test_fail_no_receivers(tmp_path: Path) -> None:
    m = _load()
    p = _write(
        tmp_path / "a.yml",
        """
        route:
          receiver: r0
        receivers: []
        """,
    )
    st, issues, _ = m.verify(p, False, {}, _alerts_minimal(tmp_path / "alerts.yml"))
    assert st == "FAIL"
    assert any("receivers" in x for x in issues)


def test_fail_no_p0_route(tmp_path: Path) -> None:
    m = _load()
    p = _write(
        tmp_path / "b.yml",
        """
        route:
          receiver: x
          group_by: [alertname]
        receivers:
          - name: x
            slack_configs: [{api_url: "https://h.example/hook"}]
        """,
    )
    st, issues, _ = m.verify(p, False, {}, _alerts_minimal(tmp_path / "alerts2.yml"))
    assert st == "FAIL"
    assert any("P0" in x or "reconcile" in x.lower() for x in issues)
