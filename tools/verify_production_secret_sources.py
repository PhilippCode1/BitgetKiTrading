#!/usr/bin/env python3
"""
Fail-closed: Production-Env-Datei prueft auf Platzhalter, Localhost/Example-Hosts in oeffentlichen
URLs, zu kurze kryptographische Werte, Fake-LLM-Provider. Gibt **keine** Secret-Werte aus, nur
redigierte Längen- und Muster-Hinweise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Wie check_production_env_template_security: typische Blocker
_PLACEHOLDER_RE = re.compile(
    r"(?i)(set[_-]?me|changeme|your[_-]?api|your[_-]?value|your[_-]?secret|"
    r"replace[_-]after|not-a-real|fake_?provider|32_chars|example\.com|"
    r"localhost|127\.0\.0\.1|::1)(?![A-Za-z0-9_])"
)

# Explizit verboten als *Wert* in Production (nicht in Keys)
_FORBIDDEN_VALUE_SUBS = (
    "<set_me",
    "your_api_key_here",
    "your_value_here",
    "your_secret_value_here",
    "your_bearer_jwt",
)

# Mindestlänge für hoch-entropische Geheimnisse
_MIN_LEN: dict[str, int] = {
    "JWT_SECRET": 32,
    "GATEWAY_JWT_SECRET": 32,
    "SECRET_KEY": 32,
    "ENCRYPTION_KEY": 32,
    "INTERNAL_API_KEY": 24,
    "ADMIN_TOKEN": 16,
    "POSTGRES_PASSWORD": 12,
    "APEX_AUDIT_LEDGER_ED25519_SEED_HEX": 32,
    "DASHBOARD_GATEWAY_AUTHORIZATION": 20,  # Bearer + jwt min rough
    "BITGET_API_KEY": 8,
    "BITGET_API_SECRET": 8,
    "BITGET_API_PASSPHRASE": 4,
    "TELEGRAM_BOT_TOKEN": 20,
    "OPENAI_API_KEY": 20,
}

# Keys deren Werte öffentliche/crawlable URLs sein sollen (kein localhost in prod-strict)
_URL_VALUE_KEYS: frozenset[str] = frozenset(
    {
        "API_GATEWAY_URL",
        "NEXT_PUBLIC_API_BASE_URL",
        "NEXT_PUBLIC_WS_BASE_URL",
        "APP_BASE_URL",
        "FRONTEND_URL",
        "VAULT_ADDR",
        "CORS_ALLOW_ORIGINS",
    }
)

_VAULT_AWARE_KEYS: frozenset[str] = frozenset(
    {
        "VAULT_ADDR",
        "VAULT_MODE",
        "VAULT_TOKEN",
        "VAULT_ROLE_ID",
        "VAULT_SECRET_ID",
        "KMS_KEY_ID",
        "AWS_SECRETS_MANAGER_SECRET_ID",
    }
)

_PUBLIC_SECRET_KEY_RE = re.compile(
    r"^NEXT_PUBLIC_.*(SECRET|TOKEN|PASSWORD|PASSPHRASE|PRIVATE|JWT|API_KEY)",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    passed: bool = True
    findings: list[str] = field(default_factory=list)
    redacted_line_hints: list[str] = field(default_factory=list)
    vault_hint: str | None = None


def _norm_val(v: str) -> str:
    t = v.strip().strip('"').strip("'")
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t


def _is_placeholder_value(val: str) -> bool:
    s = _norm_val(val)
    if not s:
        return True
    su = s.upper()
    if su in ("", "CHANGE_ME", "SET_ME", "CHANGEME"):
        return True
    for sub in _FORBIDDEN_VALUE_SUBS:
        if sub in s.lower():
            return True
    if s.startswith("<") and s.endswith(">") and "SET" in su:
        return True
    m = _PLACEHOLDER_RE.search(s)
    if m:
        return True
    return False


def _redact_value(key: str, val: str) -> str:
    s = _norm_val(val)
    if not s:
        return f"{key}=<empty> len=0"
    n = len(s)
    if n <= 4:
        return f"{key}=<redacted> len={n} alnum"
    if re.fullmatch(r"0x[0-9a-fA-F]+", s):
        return f"{key}=<redacted-hex> len={n} prefix={s[:4]}…"
    if s.lower().startswith("sk-"):
        return f"{key}=<redacted-openai-style> len={n}"
    return f"{key}=<redacted> len={n} prefix={s[:2]}…suffix={s[-2:]}"


def _has_localhostish_url(val: str) -> bool:
    u = _norm_val(val).lower()
    if "example.com" in u:
        return True
    if "localhost" in u and "file://localhost" not in u:
        return True
    if "127.0.0.1" in u or "[::1]" in u or "::1" in u:
        return True
    return False


def parse_dotenv_text(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and k not in out:
            out[k] = v
    return out


def verify_env(data: dict[str, str], *, strict: bool) -> CheckResult:
    r = CheckResult()
    vm = (_norm_val(data.get("VAULT_MODE", "none") or "none") or "none").lower()
    vaddr = data.get("VAULT_ADDR", "").strip()
    if strict and vm not in ("false", "none", "0", "off", ""):
        if not vaddr or _is_placeholder_value(vaddr):
            r.findings.append(
                "VAULT_MODE gesetzt, aber VAULT_ADDR fehlt oder Platzhalter (Vault-Modus plausibility)."
            )
            r.passed = False
    elif (
        vaddr
        and not _is_placeholder_value(vaddr)
        and vm in ("false", "none", "")
    ):
        r.vault_hint = "VAULT_ADDR ist gesetzt abweichend: prüfen, ob VAULT_MODE konsistent dokumentiert ist."

    for k, v in data.items():
        s = v.strip() if v else ""
        if strict and _PUBLIC_SECRET_KEY_RE.search(k):
            r.findings.append(
                f"public leak risk: {k} ist NEXT_PUBLIC_* und wirkt wie Secret-Schluesselname."
            )
            r.passed = False
        if strict and s and "example.com" in s.lower():
            r.findings.append(
                f"strict: 'example.com' in Wert ({k}) — erwartet echte Hosts in Production."
            )
            r.passed = False
        if (
            strict
            and s
            and _is_placeholder_value(s)
            and s not in ("false", "true", "0", "1")
        ):
            if k in (
                "LOG_LEVEL",
                "LOG_FORMAT",
                "PRODUCTION",
                "APP_ENV",
                "DEBUG",
                "NODE_ENV",
                "DEPLOY_ENV",
            ):
                pass
            else:
                r.findings.append(
                    f"verdächtiger Platzhalter/Pattern: {k} ({_redact_value(k, s)})"
                )
                r.passed = False
        minl = _MIN_LEN.get(k)
        if minl and s and not _is_placeholder_value(s):
            if s.lower().startswith("bearer "):
                tok = s[7:].strip()
                if len(tok) < minl:
                    r.findings.append(
                        f"zu kurz (nach Bearer): {k} (min {minl}) — {_redact_value(k, tok)}"
                    )
                    r.passed = False
            elif len(_norm_val(s)) < minl:
                r.findings.append(
                    f"zu kurz: {k} (min {minl}) — {_redact_value(k, s)}"
                )
                r.passed = False
        if strict and k in _URL_VALUE_KEYS and s:
            low = s.lower()
            is_internal = any(
                f"://{h}" in low
                for h in ("live-broker", "redis", "postgres", "api-gateway")
            )
            if _has_localhostish_url(s) and "docker" not in low and not is_internal:
                r.findings.append(
                    f"Produktions-URL-Key {k} enthält localhost/127.0.0.1 — {_redact_value(k, s)}"
                )
                r.passed = False
        r.redacted_line_hints.append(_redact_value(k, s) if s else f"{k}=<empty>")

    if strict:
        llm_fake = (data.get("LLM_USE_FAKE_PROVIDER", "") or "").lower()
        if llm_fake in ("1", "true", "yes"):
            r.findings.append("LLM_USE_FAKE_PROVIDER muss in Production-strict 'false' sein.")
            r.passed = False
    if r.vault_hint and strict:
        r.findings.append(r.vault_hint)
        r.passed = False
    return r


def _render_md_report(env_file: Path, strict: bool, result: CheckResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    mode = "strict" if strict else "permissive"
    findings = (
        "\n".join(f"- {item}" for item in result.findings)
        if result.findings
        else "- Keine harten Findings."
    )
    redacted = "\n".join(f"- `{line}`" for line in result.redacted_line_hints[:60])
    return (
        "# Production Secret Sources Report\n\n"
        f"- Status: **{status}**\n"
        f"- Mode: `{mode}`\n"
        f"- Env file: `{env_file.as_posix()}`\n\n"
        "## Findings\n\n"
        f"{findings}\n\n"
        "## Redacted Value Shapes (max 60)\n\n"
        f"{redacted}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Produktions-Env-Datei hart prüfen (keine Werte-Logs)."
    )
    ap.add_argument(
        "--env-file",
        type=Path,
        required=True,
        help="Z. B. .env.production (nicht committen).",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Längen-, URL-, Platzhalter- und LLM-Drift-Regeln.",
    )
    ap.add_argument(
        "--report-md",
        type=Path,
        help="Optional: redigierten Markdown-Report schreiben.",
    )
    args = ap.parse_args()
    p = args.env_file
    if not p.is_file():
        print(f"FEHLER: fehlt {p}", file=sys.stderr)
        return 2
    data = parse_dotenv_text(p.read_text(encoding="utf-8", errors="replace"))
    r = verify_env(data, strict=args.strict)
    for f in r.findings:
        print(f"FAIL: {f}", file=sys.stderr)
    if args.strict:
        print("mode=strict", file=sys.stderr)
    else:
        print("mode=permissive (nur harte Muster, ohne URL/LLM-Stricts)", file=sys.stderr)
    print("--- redacted value shapes (erste 40 Keys) ---", file=sys.stderr)
    for h in r.redacted_line_hints[:40]:
        print(f"  {h}", file=sys.stderr)
    if args.report_md is not None:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(
            _render_md_report(p, args.strict, r),
            encoding="utf-8",
        )
        print(f"Wrote {args.report_md.as_posix()}", file=sys.stderr)
    if r.passed:
        print("STATUS=PASS (keine harten Muster, Details siehe stderr).")
        return 0
    print("STATUS=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
