#!/usr/bin/env python3
"""Erzeugt kombinierte Evidence fuer Bitget-Readiness und Instrumentenkatalog."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scripts.bitget_readiness_check import build_readiness_report, load_dotenv  # noqa: E402
from scripts.refresh_bitget_asset_universe import (  # noqa: E402
    build_report_payload as build_asset_universe_payload,
    load_entries_from_json,
)
from shared_py.bitget.exchange_readiness import assess_external_key_evidence  # noqa: E402
from shared_py.bitget.instruments import (  # noqa: E402
    BitgetAssetUniverseInstrument,
    evaluate_asset_universe_live_eligibility,
)
from shared_py.live_preflight import LivePreflightContext, evaluate_live_preflight  # noqa: E402

DEFAULT_ENV_FILE = ROOT / ".env.production.example"
DEFAULT_ASSET_UNIVERSE_INPUT = ROOT / "tests" / "fixtures" / "bitget_asset_universe_sample.json"
DEFAULT_KEY_EVIDENCE = ROOT / "docs" / "production_10_10" / "bitget_key_permission_evidence.template.json"
DEFAULT_EXTERNAL_TEMPLATE = ROOT / "docs" / "production_10_10" / "bitget_exchange_instrument_evidence.template.json"

EXTERNAL_SCHEMA_VERSION = 1

REQUIRED_INSTRUMENT_BLOCK_REASONS = (
    "status_unknown",
    "status_delisted",
    "status_suspended",
    "missing_product_type_for_futures",
    "missing_margin_coin_for_futures",
    "missing_precision",
    "missing_min_qty",
    "missing_min_notional",
    "missing_data_quality_gate",
    "missing_liquidity_gate",
    "missing_risk_tier_gate",
    "missing_strategy_evidence_gate",
    "missing_owner_approval",
    "tier_0_blocked",
    "tier_4_shadow_only",
    "tier_5_blocked",
    "tier_1_requires_live_candidate_status",
)

REQUIRED_ASSET_UNIVERSE_BLOCK_REASONS = (
    "neues_asset_nicht_automatisch_live",
    "exchange_status_suspended",
    "futures_product_type_fehlt",
    "futures_margin_coin_fehlt",
    "tick_size_fehlt",
    "lot_size_fehlt",
    "risk_tier_unbekannt",
    "datenqualitaet_nicht_ok",
    "shadow_nicht_freigegeben",
)

REQUIRED_LIVE_PREFLIGHT_REASONS = (
    "bitget_readiness_not_ok",
    "asset_not_in_catalog",
    "asset_status_not_ok",
    "instrument_contract_missing",
    "instrument_metadata_stale",
)

SECRET_LIKE_KEYS = ("api_key", "secret", "passphrase", "token", "password", "authorization", "private_key")


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build_external_evidence_template() -> dict[str, Any]:
    return {
        "schema_version": EXTERNAL_SCHEMA_VERSION,
        "status": "external_required",
        "environment": "CHANGE_ME_STAGING_OR_SHADOW",
        "git_sha": "CHANGE_ME_GIT_SHA",
        "reviewed_at": "CHANGE_ME_ISO8601",
        "reviewed_by": "CHANGE_ME_EXTERNAL_OR_OWNER_REVIEWER",
        "key_permissions": {
            "read_permission": True,
            "trade_permission": True,
            "withdrawal_permission": False,
            "ip_allowlist_enabled": False,
            "account_protection_enabled": False,
            "api_version": "v2",
            "evidence_reference": "CHANGE_ME_KEY_PERMISSION_EVIDENCE_URI",
        },
        "readonly_discovery": {
            "public_time_checked": False,
            "server_time_skew_ms": None,
            "public_instruments_checked": False,
            "private_readonly_checked": False,
            "write_endpoints_called": False,
            "rate_limit_observed": False,
            "report_uri": "CHANGE_ME_READONLY_DISCOVERY_REPORT_URI",
        },
        "instrument_metadata": {
            "asset_universe_checked": False,
            "instrument_count": 0,
            "all_symbols_v2_format": False,
            "product_type_margin_coin_checked": False,
            "precision_tick_lot_min_qty_checked": False,
            "unknown_or_delisted_assets_block_live": False,
            "metadata_fresh": False,
            "report_uri": "CHANGE_ME_INSTRUMENT_METADATA_REPORT_URI",
        },
        "safety": {
            "secrets_redacted": True,
            "real_orders_possible": False,
            "owner_signoff": False,
        },
    }


def _missing_or_template(value: Any) -> bool:
    return value is None or value == "" or value == [] or str(value).startswith("CHANGE_ME")


def _secret_surface_issues(value: Any, path: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if any(marker in str(key).lower() for marker in SECRET_LIKE_KEYS):
                if isinstance(child, str) and child not in {"", "REDACTED", "[REDACTED]", "CHANGE_ME_REDACTED"}:
                    issues.append(f"{child_path}_not_redacted")
            issues.extend(_secret_surface_issues(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_secret_surface_issues(child, f"{path}[{index}]"))
    elif isinstance(value, str) and any(marker in value.lower() for marker in ("bitget_", "sk-", "eyj")):
        issues.append(f"{path}_secret_like_value")
    return issues


def assess_external_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != EXTERNAL_SCHEMA_VERSION:
        failures.append("schema_version_unbekannt")
    if payload.get("status") != "verified":
        failures.append("external_status_nicht_verified")
    for key in ("environment", "git_sha", "reviewed_at", "reviewed_by"):
        if _missing_or_template(payload.get(key)):
            failures.append(f"{key}_fehlt")

    key_permissions = payload.get("key_permissions") or {}
    for key in ("read_permission", "trade_permission"):
        if key_permissions.get(key) is not True:
            failures.append(f"key_permissions_{key}_nicht_belegt")
    for key in ("withdrawal_permission",):
        if key_permissions.get(key) is not False:
            failures.append(f"key_permissions_{key}_muss_false_sein")
    for key in ("ip_allowlist_enabled", "account_protection_enabled"):
        if key_permissions.get(key) is not True:
            failures.append(f"key_permissions_{key}_nicht_belegt")
    if key_permissions.get("api_version") != "v2":
        failures.append("key_permissions_api_version_nicht_v2")
    if _missing_or_template(key_permissions.get("evidence_reference")):
        failures.append("key_permissions_evidence_reference_fehlt")

    readonly_discovery = payload.get("readonly_discovery") or {}
    for key in ("public_time_checked", "public_instruments_checked", "private_readonly_checked"):
        if readonly_discovery.get(key) is not True:
            failures.append(f"readonly_discovery_{key}_nicht_belegt")
    if readonly_discovery.get("write_endpoints_called") is not False:
        failures.append("readonly_discovery_darf_keine_write_endpoints_aufrufen")
    skew = readonly_discovery.get("server_time_skew_ms")
    if skew is None or abs(int(skew)) > 5000:
        failures.append("readonly_discovery_server_time_skew_unbelegt_oder_zu_hoch")
    if _missing_or_template(readonly_discovery.get("report_uri")):
        failures.append("readonly_discovery_report_uri_fehlt")

    instrument_metadata = payload.get("instrument_metadata") or {}
    for key in (
        "asset_universe_checked",
        "all_symbols_v2_format",
        "product_type_margin_coin_checked",
        "precision_tick_lot_min_qty_checked",
        "unknown_or_delisted_assets_block_live",
        "metadata_fresh",
    ):
        if instrument_metadata.get(key) is not True:
            failures.append(f"instrument_metadata_{key}_nicht_belegt")
    if int(instrument_metadata.get("instrument_count") or 0) <= 0:
        failures.append("instrument_metadata_instrument_count_fehlt")
    if _missing_or_template(instrument_metadata.get("report_uri")):
        failures.append("instrument_metadata_report_uri_fehlt")

    safety = payload.get("safety") or {}
    if safety.get("secrets_redacted") is not True:
        failures.append("safety_secrets_redacted_nicht_belegt")
    if safety.get("real_orders_possible") is not False:
        failures.append("safety_real_orders_possible_muss_false_sein")
    if safety.get("owner_signoff") is not True:
        failures.append("safety_owner_signoff_fehlt")

    failures.extend(_secret_surface_issues(payload))
    return {
        "status": "PASS" if not failures else "FAIL",
        "external_required": bool(failures),
        "failures": list(dict.fromkeys(failures)),
    }


def _instrument(**overrides: Any) -> BitgetAssetUniverseInstrument:
    payload = {
        "symbol": "ETHUSDT",
        "base_coin": "ETH",
        "quote_coin": "USDT",
        "market_family": "futures",
        "product_type": "USDT-FUTURES",
        "margin_coin": "USDT",
        "margin_mode": "isolated",
        "tick_size": "0.1",
        "lot_size": "0.001",
        "min_qty": "0.001",
        "min_notional": "5",
        "price_precision": 1,
        "quantity_precision": 3,
        "status": "live_candidate",
        "asset_tier": 1,
        "is_tradable": True,
        "is_chart_visible": True,
        "data_quality_ok": True,
        "liquidity_ok": True,
        "risk_tier_assigned": True,
        "strategy_evidence_ready": True,
        "owner_approved": True,
        "source": "synthetic_contract",
    }
    payload.update(overrides)
    return BitgetAssetUniverseInstrument.model_validate(payload)


def _instrument_scenarios() -> dict[str, BitgetAssetUniverseInstrument]:
    return {
        "unknown_status": _instrument(status="unknown"),
        "delisted_status": _instrument(status="delisted"),
        "suspended_status": _instrument(status="suspended"),
        "missing_futures_product_type": _instrument(product_type=None),
        "missing_futures_margin_coin": _instrument(margin_coin=None),
        "missing_precision": _instrument(price_precision=None),
        "missing_min_qty": _instrument(min_qty=None),
        "missing_min_notional": _instrument(min_notional=None),
        "missing_data_quality": _instrument(data_quality_ok=False),
        "missing_liquidity": _instrument(liquidity_ok=False),
        "missing_risk_tier": _instrument(risk_tier_assigned=False),
        "missing_strategy_evidence": _instrument(strategy_evidence_ready=False),
        "missing_owner_approval": _instrument(owner_approved=False),
        "tier_0": _instrument(asset_tier=0),
        "tier_4_shadow_only": _instrument(asset_tier=4),
        "tier_5": _instrument(asset_tier=5),
        "tier_1_active_not_candidate": _instrument(asset_tier=1, status="active"),
    }


def _preflight_decision(
    *,
    bitget_ok: bool = True,
    asset_in_catalog: bool = True,
    asset_status_ok: bool = True,
    instrument_contract_complete: bool = True,
    instrument_metadata_fresh: bool = True,
) -> dict[str, Any]:
    decision = evaluate_live_preflight(
        LivePreflightContext(
            execution_mode_live=True,
            live_trade_enable=True,
            owner_approved=True,
            asset_in_catalog=asset_in_catalog,
            asset_status_ok=asset_status_ok,
            asset_live_allowed=True,
            instrument_contract_complete=instrument_contract_complete,
            instrument_metadata_fresh=instrument_metadata_fresh,
            data_quality_status="pass",
            liquidity_status="pass",
            slippage_ok=True,
            risk_tier_live_allowed=True,
            order_sizing_ok=True,
            portfolio_risk_ok=True,
            strategy_evidence_ok=True,
            bitget_readiness_ok=bitget_ok,
            reconcile_ok=True,
            kill_switch_active=False,
            safety_latch_active=False,
            unknown_order_state=False,
            account_snapshot_fresh=True,
            idempotency_key="idem-ok",
            audit_context_present=True,
            checked_at="synthetic-bitget-instrument-evidence",
        )
    )
    return {
        "submit_allowed": decision.submit_allowed,
        "blocking_reasons": decision.blocking_reasons,
        "missing_gates": decision.missing_gates,
    }


def build_report_payload(
    *,
    env_file: Path = DEFAULT_ENV_FILE,
    asset_universe_input: Path = DEFAULT_ASSET_UNIVERSE_INPUT,
    key_evidence_json: Path = DEFAULT_KEY_EVIDENCE,
    external_evidence_json: Path = DEFAULT_EXTERNAL_TEMPLATE,
) -> dict[str, Any]:
    readiness_report = build_readiness_report(load_dotenv(env_file), mode="dry-run")
    key_payload = json.loads(key_evidence_json.read_text(encoding="utf-8"))
    key_assessment = assess_external_key_evidence(key_payload)
    external_payload = json.loads(external_evidence_json.read_text(encoding="utf-8"))
    external_assessment = assess_external_evidence(external_payload)

    asset_universe_payload = build_asset_universe_payload(load_entries_from_json(asset_universe_input))
    asset_universe_reasons = sorted(
        {
            reason
            for asset in asset_universe_payload["assets"]
            for reason in asset.get("live_block_reasons", [])
        }
    )
    live_allowed_fixture_assets = [
        asset["symbol"] for asset in asset_universe_payload["assets"] if asset.get("live_allowed") is True
    ]

    instrument_rows: list[dict[str, Any]] = []
    for scenario_id, instrument in _instrument_scenarios().items():
        evaluated = evaluate_asset_universe_live_eligibility(instrument)
        instrument_rows.append(
            {
                "id": scenario_id,
                "symbol": evaluated.symbol,
                "is_live_allowed": evaluated.is_live_allowed,
                "block_reasons": evaluated.block_reasons,
                "preflight": _preflight_decision(
                    asset_in_catalog="status_unknown" not in evaluated.block_reasons,
                    asset_status_ok=not any(reason in evaluated.block_reasons for reason in ("status_delisted", "status_suspended")),
                    instrument_contract_complete=not any(
                        reason in evaluated.block_reasons
                        for reason in (
                            "missing_product_type_for_futures",
                            "missing_margin_coin_for_futures",
                            "missing_precision",
                            "missing_min_qty",
                            "missing_min_notional",
                        )
                    ),
                    instrument_metadata_fresh=not any(
                        reason in evaluated.block_reasons
                        for reason in (
                            "missing_data_quality_gate",
                            "missing_liquidity_gate",
                            "missing_risk_tier_gate",
                            "missing_strategy_evidence_gate",
                        )
                    ),
                ),
            }
        )

    exchange_preflight_rows = [
        {"id": "key_permission_template_missing_external", "preflight": _preflight_decision(bitget_ok=key_assessment.status == "PASS")},
        {"id": "readiness_dry_run_no_external_network", "preflight": _preflight_decision(bitget_ok=readiness_report.status == "verified")},
    ]

    covered_instrument_reasons = sorted({reason for row in instrument_rows for reason in row["block_reasons"]})
    covered_live_preflight_reasons = sorted(
        {
            reason
            for row in [*instrument_rows, *exchange_preflight_rows]
            for reason in row["preflight"]["blocking_reasons"]
        }
    )
    missing_instrument = [reason for reason in REQUIRED_INSTRUMENT_BLOCK_REASONS if reason not in covered_instrument_reasons]
    missing_asset_universe = [
        reason for reason in REQUIRED_ASSET_UNIVERSE_BLOCK_REASONS if reason not in asset_universe_reasons
    ]
    missing_preflight = [
        reason for reason in REQUIRED_LIVE_PREFLIGHT_REASONS if reason not in covered_live_preflight_reasons
    ]

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "readiness_dry_run": asdict(readiness_report),
        "key_permission_assessment": {
            "status": key_assessment.status,
            "blockers": key_assessment.blockers,
            "warnings": key_assessment.warnings,
        },
        "external_evidence_assessment": external_assessment,
        "asset_universe_summary": asset_universe_payload["summary"],
        "asset_universe_reasons": asset_universe_reasons,
        "live_allowed_fixture_assets": live_allowed_fixture_assets,
        "instrument_scenarios": instrument_rows,
        "exchange_preflight_scenarios": exchange_preflight_rows,
        "covered_instrument_block_reasons": covered_instrument_reasons,
        "missing_instrument_block_reasons": missing_instrument,
        "missing_asset_universe_block_reasons": missing_asset_universe,
        "covered_live_preflight_reasons": covered_live_preflight_reasons,
        "missing_live_preflight_reasons": missing_preflight,
        "external_required": [
            "Bitget-Key-Permission-Review mit read/trade=true, withdrawal=false, IP-Allowlist und Account-Schutz.",
            "Read-only Bitget-Discovery-Run mit Server-Time, Public Instruments und Private Read-only Account ohne Write-Endpunkte.",
            "Instrument-Metadata-Report mit v2-Symbolen, ProductType, MarginCoin, Precision, Tick/Lot/MinQty und Frischefenster.",
            "Owner-Signoff fuer Asset-Universe und Instrumentenkatalog vor Private-Live-Candidate.",
        ],
        "notes": [
            "Dieser Report nutzt nur Dry-run-/Fixture-/Template-Daten und sendet keine Orders.",
            "Echte Bitget-Readiness bleibt external_required; private Live bleibt NO_GO.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bitget Exchange Instrument Evidence Report",
        "",
        "Status: synthetischer Fail-closed-Nachweis fuer Bitget-Readiness, Key-Permissions und Instrumentenkatalog.",
        "",
        "## Summary",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Private-Live-Entscheidung: `{payload['private_live_decision']}`",
        f"- Full-Autonomous-Live: `{payload['full_autonomous_live']}`",
        f"- Runtime-Readiness-Status: `{payload['readiness_dry_run']['status']}`",
        f"- Live-Write erlaubt: `{str(payload['readiness_dry_run']['live_write_allowed']).lower()}`",
        f"- Key-Permission-Evidence: `{payload['key_permission_assessment']['status']}`",
        f"- Externe Exchange/Instrument-Evidence: `{payload['external_evidence_assessment']['status']}`",
        f"- Live-faehige Fixture-Assets: `{len(payload['live_allowed_fixture_assets'])}`",
        f"- Fehlende Instrument-Blockgruende: `{len(payload['missing_instrument_block_reasons'])}`",
        f"- Fehlende Asset-Universe-Blockgruende: `{len(payload['missing_asset_universe_block_reasons'])}`",
        f"- Fehlende Live-Preflight-Gruende: `{len(payload['missing_live_preflight_reasons'])}`",
        "",
        "## Instrument-Fail-Closed-Coverage",
        "",
        "- Abgedeckt: " + (", ".join(f"`{item}`" for item in payload["covered_instrument_block_reasons"]) or "-"),
        "- Fehlend: " + (", ".join(f"`{item}`" for item in payload["missing_instrument_block_reasons"]) or "-"),
        "",
    ]
    for row in payload["instrument_scenarios"]:
        lines.append(f"- `{row['id']}`: live_allowed=`{row['is_live_allowed']}`, Gruende={', '.join(row['block_reasons']) or '-'}")
    lines.extend(["", "## Asset-Universe-Fixture", ""])
    lines.append("- Blockgruende: " + (", ".join(f"`{item}`" for item in payload["asset_universe_reasons"]) or "-"))
    lines.append("- Live-faehige Fixture-Assets: " + (", ".join(f"`{item}`" for item in payload["live_allowed_fixture_assets"]) or "-"))
    lines.extend(["", "## Externe Evidence", ""])
    lines.append(
        "- Assessment: "
        f"`{payload['external_evidence_assessment']['status']}`; Fehler="
        + (", ".join(f"`{item}`" for item in payload["external_evidence_assessment"]["failures"]) or "-")
    )
    lines.extend(["", "## Erforderlich vor Private Live", ""])
    lines.extend(f"- {item}" for item in payload["external_required"])
    lines.extend(["", "## Einordnung", ""])
    lines.extend(f"- {item}" for item in payload["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--asset-universe-input", type=Path, default=DEFAULT_ASSET_UNIVERSE_INPUT)
    parser.add_argument("--key-evidence-json", type=Path, default=DEFAULT_KEY_EVIDENCE)
    parser.add_argument("--external-evidence-json", type=Path, default=DEFAULT_EXTERNAL_TEMPLATE)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.write_template:
        args.write_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_template.write_text(
            json.dumps(build_external_evidence_template(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"bitget_exchange_instrument_evidence_report: wrote template {args.write_template}")
        return 0

    payload = build_report_payload(
        env_file=args.env_file,
        asset_universe_input=args.asset_universe_input,
        key_evidence_json=args.key_evidence_json,
        external_evidence_json=args.external_evidence_json,
    )
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")

    internal_missing = (
        payload["missing_instrument_block_reasons"]
        + payload["missing_asset_universe_block_reasons"]
        + payload["missing_live_preflight_reasons"]
        + payload["live_allowed_fixture_assets"]
    )
    print(
        "bitget_exchange_instrument_evidence_report: "
        f"instruments={len(payload['instrument_scenarios'])} "
        f"internal_missing={len(internal_missing)} "
        f"key_status={payload['key_permission_assessment']['status']} "
        f"external_status={payload['external_evidence_assessment']['status']}"
    )
    if args.strict and internal_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
