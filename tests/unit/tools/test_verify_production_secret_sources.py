from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "verify_production_secret_sources.py"
PROD_EXAMPLE = REPO / ".env.production.example"


def test_production_template_strict_fails() -> None:
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            str(PROD_EXAMPLE),
            "--strict",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, f"Erwartet FAIL auf Platzhalter-Template, got {r.stdout!r} {r.stderr!r}"


def test_synthetic_production_file_passes_strict(tmp_path: Path) -> None:
    content = f"""
# synthetic safe-ish production-like (no real secrets, length-only check)
API_GATEWAY_URL=https://api.acme.corp
NEXT_PUBLIC_API_BASE_URL=https://api.acme.corp
NEXT_PUBLIC_WS_BASE_URL=wss://api.acme.corp
JWT_SECRET={32 * "a"}
GATEWAY_JWT_SECRET={32 * "b"}
SECRET_KEY={32 * "c"}
ENCRYPTION_KEY={32 * "d"}
INTERNAL_API_KEY={24 * "e"}
ADMIN_TOKEN={20 * "f"}
POSTGRES_PASSWORD={16 * "g"}
DASHBOARD_GATEWAY_AUTHORIZATION=Bearer {32 * "h"}
LLM_USE_FAKE_PROVIDER=false
CORS_ALLOW_ORIGINS=https://dash.acme.corp
APP_BASE_URL=https://app.acme.corp
VAULT_MODE=none
VAULT_ADDR=
""".lstrip()
    f = tmp_path / "synth.env"
    f.write_text(content, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(f), "--strict"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    err = (r.stdout or "") + (r.stderr or "")
    assert "STATUS=PASS" in r.stdout or "STATUS=PASS" in r.stderr, err
    assert r.returncode == 0, err
    out = (r.stdout + r.stderr) if r.stdout and r.stderr else (r.stdout or r.stderr)
    alnum_48 = re.search(r"sk-[a-zA-Z0-9_]{20,}\b", out) or re.search(
        r"\b[a-f0-9]{48,}\b", out, re.I
    )
    assert alnum_48 is None, "Roh-Token-ähnliches Muster in Ausgabe vermeiden (redact check)"


def test_placeholder_detected(tmp_path: Path) -> None:
    p = tmp_path / "bad.env"
    p.write_text(
        "JWT_SECRET=YOUR_API_KEY_HERE\nGATEWAY_JWT_SECRET=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "NEXT_PUBLIC_API_BASE_URL=https://api.acme.corp\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(p), "--strict"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "Platzhalter" in (r.stdout + r.stderr) or "Pattern" in (r.stdout + r.stderr)


def test_public_secret_leak_detected(tmp_path: Path) -> None:
    p = tmp_path / "leak.env"
    p.write_text(
        "NEXT_PUBLIC_API_SECRET=" + "sk-live-" + "should-never-be-public\n"
        "NEXT_PUBLIC_API_BASE_URL=https://api.acme.corp\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(p), "--strict"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "public leak risk" in (r.stdout + r.stderr)


def test_report_md_is_redacted(tmp_path: Path) -> None:
    envf = tmp_path / "prod.env"
    secret_value = "abcd" * 10
    envf.write_text(
        f"JWT_SECRET={secret_value}\nNEXT_PUBLIC_API_BASE_URL=https://api.acme.corp\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.md"
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            str(envf),
            "--strict",
            "--report-md",
            str(report),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    assert report.exists(), (r.stdout, r.stderr)
    t = report.read_text(encoding="utf-8")
    assert "Status:" in t
    assert secret_value not in t
