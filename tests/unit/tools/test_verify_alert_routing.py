from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "tools" / "verify_alert_routing.py"
TEMPLATE = REPO / "docs" / "production_10_10" / "alert_routing_evidence.template.json"


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


def _valid_delivery_evidence() -> dict[str, object]:
    m = _load()
    payload = m.build_evidence_template()
    payload.update(
        {
            "drill_started_at": "2026-04-26T00:00:00Z",
            "drill_completed_at": "2026-04-26T00:10:00Z",
            "git_sha": "84d7b66",
            "operator": "sre-review",
            "evidence_reference": "external-alert-drill-123",
            "p0_route_verified": True,
            "p1_route_verified": True,
            "kill_switch_alert_delivered": True,
            "reconcile_alert_delivered": True,
            "market_data_stale_alert_delivered": True,
            "gateway_auth_alert_delivered": True,
            "delivery_channel": "staging-slack-oncall",
            "delivery_proof_reference": "ticket-screenshot-123",
            "acknowledged_by_human": True,
            "ack_latency_seconds": 120,
            "ack_latency_budget_seconds": 900,
            "dedupe_verified": True,
            "runbook_link_verified": True,
            "main_console_alert_state_verified": True,
            "no_secret_in_alert_payload": True,
            "owner_signoff": True,
        }
    )
    return payload


def test_delivery_template_blocks_live() -> None:
    m = _load()
    status, blockers, warnings = m.assess_delivery_evidence(m.build_evidence_template())
    assert status == "FAIL"
    assert "p0_route_not_verified" in blockers
    assert "kill_switch_alert_not_delivered" in blockers
    assert "ack_latency_seconds_missing" in blockers
    assert "owner_signoff_missing_external_required" in warnings


def test_valid_delivery_evidence_passes_contract() -> None:
    m = _load()
    status, blockers, warnings = m.assess_delivery_evidence(_valid_delivery_evidence())
    assert status == "PASS"
    assert blockers == []
    assert warnings == []


def test_delivery_evidence_blocks_ack_budget_exceeded() -> None:
    m = _load()
    payload = _valid_delivery_evidence()
    payload["ack_latency_seconds"] = 1000
    status, blockers, _warnings = m.assess_delivery_evidence(payload)
    assert status == "FAIL"
    assert "ack_latency_budget_exceeded" in blockers


def test_delivery_secret_surface_blocks_unredacted_values() -> None:
    m = _load()
    assert m.secret_surface_issues({"webhook_url": "https://hooks.example/secret"}) == [
        "secret_like_field_not_redacted:webhook_url"
    ]
    assert m.secret_surface_issues({"webhook_url": "[REDACTED]", "routing_key": "not_stored_in_repo"}) == []


def test_no_secret_in_alert_payload_boolean_not_flagged_as_secret() -> None:
    m = _load()
    assert m.secret_surface_issues({"no_secret_in_alert_payload": False}) == []
    assert m.secret_surface_issues({"no_secret_in_alert_payload": True}) == []


def test_cli_template_strict_fails_and_writes_json(tmp_path: Path) -> None:
    out_json = tmp_path / "alert_routing.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--evidence-json",
            str(TEMPLATE),
            "--strict",
            "--report-md",
            str(tmp_path / "alert_routing.md"),
            "--output-json",
            str(out_json),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "p0_route_not_verified" in payload["blockers"]
    assert "kill_switch_alert_not_delivered" in payload["blockers"]
