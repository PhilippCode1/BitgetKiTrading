#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SENSITIVE_ROUTE_HINTS = (
    "/admin/",
    "/live/",
    "/live-broker/",
    "/llm/",
    "/self-healing/",
    "/health/operator-report",
    "/gateway/",
)


def _issue(issues: list[dict[str, str]], *, severity: str, code: str, message: str, path: Path | str) -> None:
    issues.append({"severity": severity, "code": code, "message": message, "path": str(path)})


def analyze(root: Path, *, strict: bool = False) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    doc = root / "docs" / "production_10_10" / "single_admin_access_control.md"
    tool_test = root / "tests" / "tools" / "test_check_single_admin_access.py"
    sec_test = root / "tests" / "security" / "test_single_admin_access_contracts.py"
    api_sec_doc = root / "docs" / "api_gateway_security.md"
    bff_auth = root / "apps" / "dashboard" / "src" / "lib" / "gateway-bff.ts"
    env_prod = root / ".env.production.example"
    env_local = root / ".env.local.example"
    helper_py = root / "shared" / "python" / "src" / "shared_py" / "single_admin_access.py"
    gw_settings = root / "config" / "gateway_settings.py"
    server_env = root / "apps" / "dashboard" / "src" / "lib" / "server-env.ts"

    for p, code, msg in (
        (doc, "doc_missing", "single_admin_access_control.md fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
        (sec_test, "security_test_missing", "Security-Test fehlt."),
        (helper_py, "single_admin_helper_missing", "single_admin_access.py fehlt."),
    ):
        if not p.is_file():
            _issue(issues, severity="error", code=code, message=msg, path=p)

    if bff_auth.is_file():
        txt = bff_auth.read_text(encoding="utf-8")
        if "DASHBOARD_GATEWAY_AUTHORIZATION fehlt" not in txt:
            _issue(
                issues,
                severity="error",
                code="missing_de_auth_error",
                message="Fehlende Gateway-Auth meldet keinen klaren deutschen Hinweis.",
                path=bff_auth,
            )
    else:
        _issue(issues, severity="error", code="bff_auth_helper_missing", message="gateway-bff.ts fehlt.", path=bff_auth)

    if gw_settings.is_file():
        gw = gw_settings.read_text(encoding="utf-8")
        if "GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN" not in gw:
            _issue(issues, severity="error", code="legacy_admin_flag_missing", message="Legacy-Admin-Flag fehlt im Gateway-Settings-Modell.", path=gw_settings)
        if "gateway_super_admin_subject" not in gw:
            _issue(issues, severity="error", code="single_admin_subject_missing", message="Single-Admin-Subject fehlt in Gateway-Settings.", path=gw_settings)
    else:
        _issue(issues, severity="error", code="gateway_settings_missing", message="config/gateway_settings.py fehlt.", path=gw_settings)

    if server_env.is_file():
        se = server_env.read_text(encoding="utf-8")
        if "gatewayAuthorizationHeader" not in se:
            _issue(issues, severity="error", code="server_gateway_auth_missing", message="serverEnv exportiert keine serverseitige Gateway-Auth.", path=server_env)
    else:
        _issue(issues, severity="error", code="server_env_missing", message="server-env.ts fehlt.", path=server_env)

    # Sensitive dashboard BFF routes need requireOperatorGatewayAuth
    route_root = root / "apps" / "dashboard" / "src" / "app" / "api" / "dashboard"
    if route_root.is_dir():
        for route in route_root.rglob("route.ts"):
            rel = "/" + str(route.relative_to(route_root)).replace("\\", "/")
            if not any(h in rel for h in SENSITIVE_ROUTE_HINTS):
                continue
            text = route.read_text(encoding="utf-8")
            if "requireOperatorGatewayAuth(" not in text:
                sev = "error" if strict else "warning"
                _issue(
                    issues,
                    severity=sev,
                    code="sensitive_route_without_auth_guard",
                    message="Sensitive BFF route without requireOperatorGatewayAuth().",
                    path=route,
                )
    else:
        _issue(issues, severity="error", code="dashboard_api_missing", message="apps/dashboard/src/app/api/dashboard fehlt.", path=route_root)

    for env_path, label in ((env_prod, ".env.production.example"), (env_local, ".env.local.example")):
        if not env_path.is_file():
            _issue(issues, severity="error", code="env_missing", message=f"{label} fehlt.", path=env_path)
            continue
        txt = env_path.read_text(encoding="utf-8")
        for m in re.finditer(r"(?mi)^\s*(NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|JWT|AUTHORIZATION)[A-Z0-9_]*)\s*=", txt):
            _issue(
                issues,
                severity="error",
                code="public_secret_env_name",
                message=f"{label}: NEXT_PUBLIC Secret/Token-Name unzulässig ({m.group(1)}).",
                path=env_path,
            )
        if label == ".env.production.example":
            if re.search(r"(?mi)^\s*GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN\s*=\s*true\s*$", txt):
                _issue(
                    issues,
                    severity="error",
                    code="legacy_admin_enabled_in_production_example",
                    message="Production-Example erlaubt Legacy-Admin-Token.",
                    path=env_path,
                )
            if "DASHBOARD_GATEWAY_AUTHORIZATION=Bearer" not in txt:
                _issue(
                    issues,
                    severity="error",
                    code="dashboard_gateway_auth_missing_in_prod_env",
                    message="DASHBOARD_GATEWAY_AUTHORIZATION fehlt im Production-Example.",
                    path=env_path,
                )

    if api_sec_doc.is_file():
        sec_txt = api_sec_doc.read_text(encoding="utf-8").lower()
        if "dashboard_gateway_authorization" not in sec_txt:
            _issue(
                issues,
                severity="error",
                code="api_gateway_doc_missing_dashboard_auth",
                message="api_gateway_security.md erwähnt DASHBOARD_GATEWAY_AUTHORIZATION nicht.",
                path=api_sec_doc,
            )
    else:
        _issue(issues, severity="error", code="api_gateway_doc_missing", message="docs/api_gateway_security.md fehlt.", path=api_sec_doc)

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    return {
        "ok": len(errors) == 0 and (not strict or len(warnings) == 0),
        "strict": strict,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Single-Admin Auth/Access-Control für die private Main Console.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze(ROOT, strict=args.strict)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_single_admin_access: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']} strict={str(args.strict).lower()}"
        )
        for it in payload["issues"]:
            print(f"{it['severity'].upper()} {it['code']}: {it['message']} [{it['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
