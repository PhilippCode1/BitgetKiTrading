from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_checker():
    root = Path(__file__).resolve().parents[2]
    checker_path = root / "tools" / "check_single_owner_scope.py"
    spec = importlib.util.spec_from_file_location("check_single_owner_scope", checker_path)
    if spec is None or spec.loader is None:
        raise AssertionError("checker import failed")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> Path:
    _write(tmp_path / "docs/production_10_10/single_owner_product_scope.md", "Philipp Crljic\nkein SaaS\n")
    _write(tmp_path / "docs/production_10_10/main_console_product_direction.md", "private Owner-Nutzung\n")
    _write(
        tmp_path / "apps/dashboard/src/middleware.ts",
        'const LEGACY_SCOPE_BLOCKED_PREFIXES=["/portal","/console/account/billing","/console/account/payments","/console/admin/billing","/console/admin/commerce-payments","/console/admin/customers"];',
    )
    _write(
        tmp_path / "apps/dashboard/src/lib/main-console/navigation.ts",
        'export const MAIN_CONSOLE_PRIMARY_SECTIONS=[{links:[{href:"/console/health"}]}];',
    )
    _write(tmp_path / "apps/dashboard/src/components/layout/SidebarNav.tsx", "export const x = 1;")
    _write(tmp_path / "apps/dashboard/src/messages/de.json", '{"console":{"nav":{"health":"Systemzustand"}}}')
    _write(tmp_path / "README.md", "Private Nutzung ohne Kundenrollen.")
    _write(tmp_path / ".env.example", "PAYMENT_STRIPE_ENABLED=false\n")
    return tmp_path


def test_active_billing_in_navigation_detected(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(
        root / "apps/dashboard/src/lib/main-console/navigation.ts",
        'export const x=[{href:"/console/account/billing"}];',
    )
    out = mod.analyze(root, strict=True)
    assert any(i["code"] == "active_navigation_term" for i in out["issues"])


def test_active_pricing_in_ui_detected(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / "apps/dashboard/src/app/(operator)/console/pricing/page.tsx", "x")
    out = mod.analyze(root, strict=True)
    assert any(i["code"] == "active_route_sales_term" for i in out["issues"])


def test_payment_env_required_detected(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / ".env.production.example", "PAYMENT_STRIPE_ENABLED=true\n")
    out = mod.analyze(root, strict=True)
    assert any(i["code"] == "payment_env_enabled" for i in out["issues"])


def test_historical_mention_allowed_in_legacy_docs(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / "docs/archive/legacy_billing.md", "billing customer checkout")
    out = mod.analyze(root, strict=True)
    assert out["error_count"] == 0


def test_private_scope_doc_recognized(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    out = mod.analyze(root, strict=True)
    assert out["error_count"] == 0


def test_old_customer_live_text_detected(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / "apps/dashboard/src/app/(operator)/console/customer-live/page.tsx", "x")
    out = mod.analyze(root, strict=True)
    assert any(i["code"] == "active_route_sales_term" for i in out["issues"])


def test_owner_gate_term_allowed(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / "apps/dashboard/src/app/(operator)/console/ops/page.tsx", "owner_gate private_runtime_gate")
    out = mod.analyze(root, strict=True)
    assert out["error_count"] == 0


def test_checker_json_parseable() -> None:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "tools" / "check_single_owner_scope.py"), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)


def test_strict_fails_on_sales_language(tmp_path: Path) -> None:
    mod = _load_checker()
    root = _minimal_repo(tmp_path)
    _write(root / "apps/dashboard/src/app/(operator)/console/subscription/page.tsx", "x")
    out = mod.analyze(root, strict=True)
    assert out["ok"] is False


def test_tests_do_not_require_new_customer_billing() -> None:
    checker = Path("tools/check_single_owner_scope.py").read_text(encoding="utf-8").lower()
    assert "customer_payment_required" not in checker
