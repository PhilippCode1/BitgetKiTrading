#!/usr/bin/env python3
"""Kombinierter Evidence-Report: German-only UI (Scanner + Sprach-Policy + externe Owner-UAT)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "python" / "src"
for p in (ROOT, SHARED):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.check_german_only_ui import (  # noqa: E402
    DASHBOARD_SRC_DEFAULT,
    GLOSSARY_DOC_DEFAULT,
    MESSAGES_DIR_DEFAULT,
    POLICY_DOC_DEFAULT,
    analyze_german_ui,
)
from tools.check_german_ui_language import analyze as analyze_german_ui_language  # noqa: E402

DEFAULT_UAT = ROOT / "docs" / "production_10_10" / "german_only_ui_uat.template.json"
UAT_SCHEMA = 1


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _missing_or_template(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        t = v.strip()
        return t == "" or t.startswith("CHANGE_ME")
    return False


def assess_uat_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if payload.get("schema_version") != UAT_SCHEMA:
        failures.append("schema_version")
    if payload.get("status") != "verified":
        failures.append("status_nicht_verified")
    for k in ("reviewed_by", "reviewed_at", "environment", "git_sha"):
        if _missing_or_template(payload.get(k)):
            failures.append(f"{k}_fehlt")

    mc = payload.get("main_console") or {}
    for k, code in (
        ("all_visible_labels_german_or_documented", "main_console_labels"),
        ("no_english_marketing_phrases_in_operator_flow", "main_console_marketing_en"),
        ("legacy_commerce_routes_acknowledged", "legacy_ack"),
    ):
        if mc.get(k) is not True:
            failures.append(code)

    sp = payload.get("spot_checks") or {}
    for k, code in (
        ("navigation_matches_policy", "nav_policy"),
        ("safety_states_readable_de", "safety_de"),
        ("error_messages_not_english_only", "errors_de"),
    ):
        if sp.get(k) is not True:
            failures.append(code)

    saf = payload.get("safety") or {}
    if saf.get("no_secrets_in_screenshots") is not True:
        failures.append("secrets_in_uat")
    if saf.get("owner_signoff") is not True:
        failures.append("owner_signoff")

    return {
        "status": "PASS" if not failures else "FAIL",
        "external_required": bool(failures),
        "failures": list(dict.fromkeys(failures)),
    }


def build_report_payload(*, uat_json: Path = DEFAULT_UAT) -> dict[str, Any]:
    surface = analyze_german_ui(
        dashboard_src=DASHBOARD_SRC_DEFAULT,
        messages_dir=MESSAGES_DIR_DEFAULT,
        policy_doc=POLICY_DOC_DEFAULT,
        glossary_doc=GLOSSARY_DOC_DEFAULT,
    )
    language = analyze_german_ui_language()
    uat_raw = json.loads(uat_json.read_text(encoding="utf-8"))
    uat = assess_uat_evidence(uat_raw)

    internal: list[str] = []
    if not surface.get("ok"):
        internal.append("check_german_only_ui_errors")
    if surface.get("error_count", 0) > 0:
        internal.append("german_only_scan_errors")
    if not language.get("ok"):
        internal.append("check_german_ui_language_errors")
    if language.get("error_count", 0) > 0:
        internal.append("german_ui_language_errors")

    return {
        "generated_at": _now(),
        "git_sha": _git_sha(),
        "private_live_decision": "NO_GO",
        "full_autonomous_live": "NO_GO",
        "german_only_scan": {
            "ok": surface.get("ok"),
            "files_scanned": surface.get("files_scanned"),
            "error_count": surface.get("error_count"),
            "warning_count": surface.get("warning_count"),
        },
        "german_ui_language": {
            "ok": language.get("ok"),
            "error_count": language.get("error_count"),
            "warning_count": language.get("warning_count"),
        },
        "owner_uat_assessment": uat,
        "internal_issues": internal,
        "external_required": [
            "Owner-UAT der Hauptkonsole (sichtbare Texte, Safety-Labels, kein reines Englisch im Operatorfluss).",
            "UAT-JSON mit status=verified und Signoff, ohne Screenshots mit Secrets.",
        ],
        "recommended_commands": [
            "python tools/check_german_only_ui.py --strict",
            "python tools/check_german_ui_language.py --strict",
            "pytest tests/tools/test_check_german_only_ui.py -q",
            "pytest tests/tools/test_check_german_ui_language.py -q",
        ],
        "notes": [
            "Repo-Scanner ersetzen keine manuelle Prüfung von Dynamic Content und leeren Zuständen.",
            "Legacy-Commerce-Routen sind im Scanner von Out-of-Scope-Warnungen ausgenommen; Hauptkonsole bleibt Regelfläche.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    u = payload["owner_uat_assessment"]
    lines = [
        "# German-only UI Evidence Report",
        "",
        f"- Erzeugt: `{payload['generated_at']}` · SHA `{payload['git_sha']}`",
        f"- `check_german_only_ui`: ok=`{payload['german_only_scan']['ok']}` "
        f"errors={payload['german_only_scan']['error_count']}",
        f"- `check_german_ui_language`: ok=`{payload['german_ui_language']['ok']}` "
        f"errors={payload['german_ui_language']['error_count']}",
        f"- Owner-UAT-Template: `{u['status']}` ({len(u.get('failures') or [])} Abweichungen)",
        f"- Interne Issues: {len(payload['internal_issues'])}",
        "",
        "## Interne Issues",
        "",
    ]
    lines.extend(f"- `{x}`" for x in (payload["internal_issues"] or ["- keine -"]))
    lines.extend(["", "## Erforderlich extern", ""])
    lines.extend(f"- {x}" for x in payload["external_required"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uat-json", type=Path, default=DEFAULT_UAT)
    p.add_argument("--output-md", type=Path)
    p.add_argument("--output-json", type=Path)
    p.add_argument("--write-uat-template", type=Path)
    p.add_argument("--strict", action="store_true", help="Bei internen Scan-Fehlern Exit 1.")
    p.add_argument(
        "--strict-external",
        action="store_true",
        help="Zusaetzlich: Owner-UAT JSON muss assess_uat_evidence PASS erfuellen.",
    )
    args = p.parse_args(argv)

    if args.write_uat_template:
        tpath = args.write_uat_template
        if tpath.is_dir():
            tpath = tpath / "german_only_ui_uat.template.json"
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "external_required",
                    "reviewed_by": "CHANGE_ME_OWNER",
                    "reviewed_at": "CHANGE_ME_ISO8601",
                    "environment": "CHANGE_ME_STAGING_OR_LOCAL",
                    "git_sha": "CHANGE_ME_GIT_SHA",
                    "main_console": {
                        "all_visible_labels_german_or_documented": False,
                        "no_english_marketing_phrases_in_operator_flow": False,
                        "legacy_commerce_routes_acknowledged": False,
                    },
                    "spot_checks": {
                        "navigation_matches_policy": False,
                        "safety_states_readable_de": False,
                        "error_messages_not_english_only": False,
                    },
                    "safety": {
                        "no_secrets_in_screenshots": True,
                        "owner_signoff": False,
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"german_only_ui_evidence_report: wrote {tpath}")
        return 0

    payload = build_report_payload(uat_json=args.uat_json)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(
        "german_only_ui_evidence_report: internal="
        f"{len(payload['internal_issues'])} uat={payload['owner_uat_assessment']['status']}"
    )
    if args.strict and payload["internal_issues"]:
        return 1
    if args.strict_external and payload["owner_uat_assessment"]["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
