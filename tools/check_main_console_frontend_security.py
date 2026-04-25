#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PUBLIC_ENV = re.compile(
    r"(?mi)^\s*(NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|JWT|AUTHORIZATION|PASSWORD|PASS|REDIS|DB|OPENAI)[A-Z0-9_]*)\s*="
)

FORBIDDEN_UI_TERMS = ("billing", "customer", "customers", "subscription", "pricing", "checkout", "saas")
MAIN_CONSOLE_ACTIVE_ROOTS = (
    "app/(operator)/console/",
    "components/console/",
    "components/layout/",
    "lib/main-console/",
)
LEGACY_ALLOWED_PATH_PARTS = (
    "/console/account/",
    "/console/admin/",
    "/account/",
    "/admin/",
    "customer-portal",
    "contract",
    "commerce",
)


def _issue(issues: list[dict[str, str]], *, severity: str, code: str, message: str, path: Path | str) -> None:
    issues.append({"severity": severity, "code": code, "message": message, "path": str(path)})


def _scan_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def analyze(root: Path, *, strict: bool = False) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    required = (
        (root / "docs" / "production_10_10" / "main_console_frontend_bff_security.md", "doc_missing", "Frontend/BFF-Sicherheitsdoku fehlt."),
        (root / "tools" / "check_main_console_frontend_security.py", "tool_missing", "Frontend-Security-Checker fehlt."),
        (root / "tests" / "tools" / "test_check_main_console_frontend_security.py", "tool_test_missing", "Tool-Test für Frontend-Security fehlt."),
        (root / "apps" / "dashboard" / "src" / "lib" / "server-env.ts", "server_env_missing", "server-env.ts fehlt."),
        (root / "apps" / "dashboard" / "src" / "lib" / "gateway-bff.ts", "gateway_bff_missing", "gateway-bff.ts fehlt."),
    )
    for p, code, msg in required:
        if not p.is_file():
            _issue(issues, severity="error", code=code, message=msg, path=p)

    # NEXT_PUBLIC secret names in env examples.
    for env_path in root.glob(".env*.example"):
        txt = _scan_text_file(env_path)
        for m in FORBIDDEN_PUBLIC_ENV.finditer(txt):
            _issue(
                issues,
                severity="error",
                code="dangerous_next_public_name",
                message=f"Gefährlicher NEXT_PUBLIC-Name: {m.group(1)}",
                path=env_path,
            )

    dashboard_src = root / "apps" / "dashboard" / "src"
    if dashboard_src.is_dir():
        for tsx in dashboard_src.rglob("*.[tj]s*"):
            txt = _scan_text_file(tsx)
            if not txt:
                continue
            if "dangerouslySetInnerHTML" in txt:
                _issue(
                    issues,
                    severity="error",
                    code="dangerous_html_injection",
                    message="dangerouslySetInnerHTML gefunden.",
                    path=tsx,
                )
            if re.search(r"target\s*=\s*['_\"]_blank['_\"]", txt) and "rel=" not in txt:
                sev = "error" if strict else "warning"
                _issue(
                    issues,
                    severity=sev,
                    code="blank_target_without_rel",
                    message="Link mit target=_blank ohne rel gefunden.",
                    path=tsx,
                )
            if "console.log(" in txt and re.search(r"(?i)(secret|token|authorization|api[_-]?key|passphrase|payload)", txt):
                sev = "error" if strict else "warning"
                _issue(
                    issues,
                    severity=sev,
                    code="console_log_potential_secret",
                    message="console.log mit potenziell sensitiven Begriffen gefunden.",
                    path=tsx,
                )

            lowered = txt.lower()
            rel = str(tsx.relative_to(dashboard_src)).replace("\\", "/")
            is_main_console_active = any(rel.startswith(p) for p in MAIN_CONSOLE_ACTIVE_ROOTS)
            if is_main_console_active and any(term in lowered for term in FORBIDDEN_UI_TERMS):
                if not any(p.strip("/") in rel for p in LEGACY_ALLOWED_PATH_PARTS):
                    _issue(
                        issues,
                        severity="info",
                        code="forbidden_commercial_ui_term",
                        message="Aktive Main-Console-Datei enthält Billing/Customer/SaaS-Begriffe.",
                        path=tsx,
                    )
    else:
        _issue(issues, severity="error", code="dashboard_src_missing", message="apps/dashboard/src fehlt.", path=dashboard_src)

    # Server-only BFF guard contract.
    bff = root / "apps" / "dashboard" / "src" / "lib" / "gateway-bff.ts"
    if bff.is_file():
        txt = _scan_text_file(bff)
        if "requireOperatorGatewayAuth" not in txt:
            _issue(issues, severity="error", code="missing_bff_auth_guard", message="requireOperatorGatewayAuth fehlt.", path=bff)
        if "DASHBOARD_GATEWAY_AUTHORIZATION fehlt" not in txt:
            _issue(
                issues,
                severity="error",
                code="missing_german_auth_error",
                message="Deutsche Fehlermeldung für fehlende Gateway-Auth fehlt.",
                path=bff,
            )

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
    parser = argparse.ArgumentParser(description="Prüft Frontend/BFF-Sicherheit der Main Console.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = analyze(ROOT, strict=args.strict)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_main_console_frontend_security: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']} strict={str(args.strict).lower()}"
        )
        for item in payload["issues"]:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']} [{item['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
