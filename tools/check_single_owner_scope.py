#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

BANNED_TERMS = (
    "billing",
    "customer",
    "kunden",
    "pricing",
    "payment",
    "subscription",
    "checkout",
    "saas",
    "trial",
)

LEGACY_ALLOWED_PREFIXES = (
    "apps/dashboard/src/app/(customer)/",
    "apps/dashboard/src/app/(operator)/console/account/billing/",
    "apps/dashboard/src/app/(operator)/console/account/payments/",
    "apps/dashboard/src/app/(operator)/console/admin/billing/",
    "apps/dashboard/src/app/(operator)/console/admin/commerce-payments/",
    "apps/dashboard/src/app/(operator)/console/admin/customers/",
    "apps/dashboard/src/app/(operator)/console/admin/contracts/",
    "docs/archive/",
)

def _is_legacy_allowed(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in LEGACY_ALLOWED_PREFIXES)


def _contains_banned_term(text: str) -> str | None:
    lowered = text.lower()
    for term in BANNED_TERMS:
        if term in lowered:
            return term
    return None


def analyze(root: Path, *, strict: bool = False) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    scope_doc = root / "docs" / "production_10_10" / "single_owner_product_scope.md"
    main_console_doc = root / "docs" / "production_10_10" / "main_console_product_direction.md"
    middleware = root / "apps" / "dashboard" / "src" / "middleware.ts"
    nav = root / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"

    if not scope_doc.is_file():
        issues.append({"severity": "error", "code": "scope_doc_missing", "message": "single_owner_product_scope.md fehlt.", "path": str(scope_doc)})
    else:
        txt = scope_doc.read_text(encoding="utf-8").lower()
        if "philipp crljic" not in txt or "kein saas" not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "scope_doc_incomplete",
                    "message": "Scope-Doku nennt private Nutzung/kein SaaS nicht klar genug.",
                    "path": str(scope_doc),
                }
            )

    if not main_console_doc.is_file():
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console_doc)})
    else:
        txt = main_console_doc.read_text(encoding="utf-8").lower()
        if "private owner-nutzung" not in txt and "private" not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "main_console_private_missing",
                    "message": "Main-Console-Doku erwähnt private Nutzung nicht.",
                    "path": str(main_console_doc),
                }
            )

    if not middleware.is_file():
        issues.append({"severity": "error", "code": "middleware_missing", "message": "Dashboard-Middleware fehlt.", "path": str(middleware)})
    else:
        txt = middleware.read_text(encoding="utf-8")
        for required in (
            '"/portal"',
            '"/console/account/billing"',
            '"/console/account/payments"',
            '"/console/admin/billing"',
            '"/console/admin/commerce-payments"',
            '"/console/admin/customers"',
        ):
            if required not in txt:
                issues.append(
                    {
                        "severity": "error",
                        "code": "legacy_block_missing",
                        "message": f"Legacy-Scope-Block fehlt: {required}",
                        "path": str(middleware),
                    }
                )

    if nav.is_file():
        nav_txt = nav.read_text(encoding="utf-8")
        hrefs: list[str] = []
        for m in re.finditer(r'href:\s*(?:"([^"]+)"|`([^`]+)`)', nav_txt):
            href = m.group(1) or m.group(2) or ""
            if href:
                hrefs.append(href)
        for href in hrefs:
            h = href.lower()
            if any(term in h for term in ("billing", "customer", "payment", "pricing", "subscription", "checkout", "saas")):
                issues.append(
                    {
                        "severity": "error",
                        "code": "active_navigation_term",
                        "message": f"Aktive Navigation enthält verbotenen Begriff in href: {href}",
                        "path": str(nav),
                    }
                )

    # Routen-Pfade mit banned terms, sofern nicht legacy-allowed
    app_root = root / "apps" / "dashboard" / "src" / "app"
    if app_root.is_dir():
        for page in app_root.rglob("page.tsx"):
            rel = str(page.relative_to(root)).replace("\\", "/")
            if _is_legacy_allowed(rel):
                continue
            rel_lower = rel.lower()
            hit = None
            for term in BANNED_TERMS:
                if f"/{term}" in rel_lower or f"-{term}" in rel_lower or f"_{term}" in rel_lower:
                    hit = term
                    break
            if hit:
                sev = "error" if strict else "warning"
                issues.append(
                    {
                        "severity": sev,
                        "code": "active_route_sales_term",
                        "message": f"Aktive Route enthält Begriff '{hit}'.",
                        "path": str(page),
                    }
                )

    # ENV-Beispiele: keine Payment-Pflicht fuer private Nutzung
    for env_name in (".env.example", ".env.local.example", ".env.production.example", ".env.test.example", ".env.shadow.example"):
        env_path = root / env_name
        if not env_path.is_file():
            continue
        txt = env_path.read_text(encoding="utf-8")
        if re.search(r"(?mi)^PAYMENT_(?:STRIPE|CHECKOUT|WISE|PAYPAL).*ENABLED=true\s*$", txt):
            issues.append(
                {
                    "severity": "error",
                    "code": "payment_env_enabled",
                    "message": f"{env_name}: PAYMENT_* darf nicht als Pflicht aktiv sein.",
                    "path": str(env_path),
                }
            )
        if re.search(r"(?mi)PAYMENT_.*(pflicht|required|must)", txt):
            issues.append(
                {
                    "severity": "error",
                    "code": "payment_env_required_language",
                    "message": f"{env_name}: Payment-Pflichtsprache erkannt.",
                    "path": str(env_path),
                }
            )

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    return {
        "ok": len(errors) == 0 and (not strict or len(warnings) == 0),
        "strict": strict,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "legacy_allowed_prefixes": list(LEGACY_ALLOWED_PREFIXES),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Single-Owner-Produkt-Scope ohne aktive SaaS/Billing-Pfade.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = analyze(ROOT, strict=args.strict)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_single_owner_scope: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']} strict={str(args.strict).lower()}"
        )
        for issue in payload["issues"]:
            print(f"{issue['severity'].upper()} {issue['code']}: {issue['message']} [{issue['path']}]")

    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
