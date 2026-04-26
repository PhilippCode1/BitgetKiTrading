#!/usr/bin/env python3
"""
CI-Gate: ENV-Vorlagen ohne aktive Security-Flags und ohne erkennbare Geheimnisse.

Prueft .env.example, .env.production.example, .env.shadow.example auf:
- verbotene Prod-/Shadow-Flags (DEBUG=true, API_AUTH_MODE=none, …)
- typische API-Key-/Token-Muster (OpenAI sk-*, Bitget-artige Mocks, alte Mock-Praefixe)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (ENV-NAME, verbotener Wert nach Normalisierung — upper)
_FORBIDDEN: tuple[tuple[str, str], ...] = (
    ("SECURITY_ALLOW_EVENT_DEBUG_ROUTES", "TRUE"),
    ("SECURITY_ALLOW_DB_DEBUG_ROUTES", "TRUE"),
    ("SECURITY_ALLOW_ALERT_REPLAY_ROUTES", "TRUE"),
    ("DEBUG", "TRUE"),
    ("API_AUTH_MODE", "NONE"),
    ("LLM_USE_FAKE_PROVIDER", "TRUE"),
    ("BITGET_DEMO_ENABLED", "TRUE"),
    ("TELEGRAM_DRY_RUN", "TRUE"),
    ("NEWS_FIXTURE_MODE", "TRUE"),
    ("PAPER_SIM_MODE", "TRUE"),
)

# Nur Prod-/Shadow: strenge Sicherheits-Flags
_TEMPLATES_STRICT: tuple[Path, ...] = (
    ROOT / ".env.production.example",
    ROOT / ".env.shadow.example",
)

# Inkl. .env.example: keine Secrets in Mustern, auch in lokalen Vorlagen
_TEMPLATES_SECRET_SCAN: tuple[Path, ...] = _TEMPLATES_STRICT + (ROOT / ".env.example",)

# Erlaubte reine Platzhalter (Gross-Kleinschreibung in _norm_val gespiegelt)
_PLACEHOLDER_MARKERS: frozenset[str] = frozenset(
    {
        "",
        "CHANGEME",
        "CHANGE_ME",
        "SET_ME",
        "SETMEFROMDISCOVERY",
        "JWT_MIT_GATEWAY_ROLES",  # legacy: .env.example BFF-Hinweis-Token-Label
        "YOUR_API_KEY_HERE",
        "YOUR_SECRET_VALUE_HERE",
        "YOUR_VALUE_HERE",
        "YOUR_VALUE_OR_BLANK",  # Redis-Pass z. B. leer
        "YOUR_BEARER_JWT",
    }
)


def _norm_val(v: str) -> str:
    t = v.strip()
    t = t.strip('"').strip("'")
    t = t.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t


def _is_allowed_placeholder_value(val_u: str) -> bool:
    s = _norm_val(val_u)
    su = s.upper()
    if su in _PLACEHOLDER_MARKERS:
        return True
    if s.startswith("<") and s.endswith(">") and "SET" in su:
        return True
    if s.startswith("<") and s.endswith(">") and "CHANGEME" in su:
        return True
    if s.startswith("<") and s.endswith(">") and "OR_" in su:
        return True  # <SET_ME_or_blank>
    if s.startswith("<") and s.endswith(">") and "MEFROM" in su:
        return True  # <SET_*_FROM_DISCOVERY> etc.
    if s.startswith("<") and s.endswith(">") and "JWT" in su:
        return True  # <jwt_mit_gateway_roles> o.a.
    if su.startswith((
        "HTTP://", "HTTPS://", "WS://", "WSS://",
    )):
        return True
    if s.startswith("postgresql://") and "<" in s and ">" in s:
        return True
    if s.startswith("redis://"):
        return True
    if su in ("RASTER",) or s == "none":
        return True
    return False


# Alte Mocks: wirklich in Prod nie verwenden, auch nicht als "Syntax only"
_DANGEROUS_VALUE_SUBSTR: tuple[str, ...] = (
    "prod_ex_only",
    "shadow_ex_only",
    "not-a-real-key",
    "replace_after_mint",  # dummy JWT-Fragment
)

# OpenAI: klassische User/Service-Key Laenge 51 = sk- + 48; plus proj- scoped-Varianten
_PAT_OPENAI: tuple[re.Pattern[str], str] = (
    (
        re.compile(
            r"(?i)sk-\s*(?:proj|ant|test|live|or-v1|svcacct)\s*-\s*[A-Za-z0-9_\-]+"
        ),
        "OpenAI/vendor sk-(proj|ant|test|...)- style key",
    ),
    # sk- + genau 48 alnum (Vorlagen ohne reale Muster)
    (re.compile(r"(?i)\bsk-[a-zA-Z0-9]{48}\b"), "OpenAI-User-Key (sk- + 48)"),
    (
        re.compile(r"(?i)\bsk-(?:[A-Za-z0-9_-]){20,}\b"),
        "OpenAI-style `sk-` + long alnum token (use YOUR_API_KEY_HERE in templates)",
    ),
)

# JWT-artig: drei Base64url-Segmente (Committ echter/Beispiel-Tokens verhindern)
_PAT_JWT_THREE: re.Pattern[str] = re.compile(
    r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
)

# Heuristik: Bitget – KEY/SECRET/PASSPHRASE/Signatur, Base64- oder Hex-Last
_PAT_BITGET_EQ: tuple[re.Pattern[str], str] = (
    (
        re.compile(
            r"(?i)^[A-Z_]*BITGET_(?:DEMO_)?(?:API_)?KEY\s*=\s*"
            r"([A-Za-z0-9+/=]{20,200})\s*$"
        ),
        "BITGET_*_KEY: konkreter Wert; nutze YOUR_API_KEY_HERE",
    ),
    (
        re.compile(
            r"(?i)^[A-Z_]*BITGET_(?:DEMO_)?(?:API_)?SECRET\s*=\s*"
            r"([A-Za-z0-9+/=]{20,200})\s*$"
        ),
        "BITGET_*_SECRET: verdaechtig laange Zeichenkette; Platzhalter verwenden",
    ),
    (
        re.compile(
            r"(?i)^[A-Z_]*BITGET_(?:DEMO_)?(?:API_)?PASSPHRASE\s*=\s*"
            r"([^\s#]{12,200})\s*$"
        ),
        "BITGET_*_PASSPHRASE: ab 12 Nicht-Whitespace; Platzhalter verwenden",
    ),
)


def _forbidden_secrets_in_line(key: str, val_raw: str) -> list[str]:
    """Wert- und (bei Bitget) Key=Wert-Zeile pruefen; val_raw = RHS."""
    if _is_allowed_placeholder_value(val_raw):
        return []
    msg: list[str] = []
    l_raw = val_raw
    l_norm = _norm_val(val_raw)
    l_u = l_raw.upper()
    full_eq = f"{key.strip()}={val_raw.strip()}"

    for sub in _DANGEROUS_VALUE_SUBSTR:
        if sub.upper() in l_u:
            msg.append(f"enthaelt verbotene Mock-Teilfolge: {sub!r}")

    for pat, desc in _PAT_OPENAI:
        if pat.search(l_raw) or (l_norm and pat.search(l_norm)):
            msg.append(desc)
            break

    if re.search(r"rk_(?:live|test)_[A-Za-z0-9]{20,}", l_raw):
        msg.append("Stripe restricted key; nur Platzhalter in Vorlagen")
    if re.search(
        r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}\b",
        l_raw,
    ):
        msg.append("Stripe sk_/pk_ live/test key; nur YOUR_* Platzhalter in Vorlagen")

    for pat_bg, desc_bg in _PAT_BITGET_EQ:
        m_bg = pat_bg.search(full_eq)
        if not m_bg or l_raw.strip().endswith(">"):
            continue
        b = m_bg.group(1)
        if _is_allowed_placeholder_value(b):
            break
        if b.upper() not in _PLACEHOLDER_MARKERS and "<" not in b:
            if not (b.startswith("<") and b.endswith(">")):
                msg.append(desc_bg)
        break

    for chunk in (l_raw, l_norm):
        m = _PAT_JWT_THREE.search(chunk)
        if m and len(m.group(0)) > 30:
            c_up = chunk.upper()
            if "JWT_MIT" in c_up or (chunk.strip().startswith("<") and ">" in chunk):
                continue
            msg.append("Wert enthaelt JWT-Fragment (eyJ…; nur CHANGEME/Platzhalter)")

    return msg


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _check_forbidden_flags(path: Path) -> list[str]:
    if not path.is_file():
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        return [f"fehlt: {rel}"]
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key_u = key.strip().upper()
        val_u = val.strip().strip('"').strip("'").upper()
        for fk, fv in _FORBIDDEN:
            if key_u == fk and val_u == fv:
                msg = (
                    f"{path.name}:{lineno}: {fk}={val.strip()} "
                    "(in Prod/Shadow verboten)"
                )
                errors.append(msg)
    return errors


def _check_secrets_in_templates(path: Path) -> list[str]:
    if not path.is_file():
        return []
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    parsed: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        env_key, _, val = line.partition("=")
        parsed[env_key.strip()] = val.strip()
        if path.name == ".env.production.example" and env_key.strip().upper().endswith("_URL"):
            lowered = val.strip().lower()
            if "localhost" in lowered or "127.0.0.1" in lowered:
                if "fixture" not in env_key.strip().lower() and "fixture" not in lowered:
                    errors.append(
                        f"{path.name}:{lineno}: localhost/127.0.0.1 in Production-URL ohne expliziten Fixture-Kontext"
                    )
        if env_key.strip().upper().startswith("NEXT_PUBLIC_"):
            ukey = env_key.strip().upper()
            if any(item in ukey for item in ("SECRET", "TOKEN", "API_KEY", "JWT", "PASSPHRASE", "INTERNAL")):
                errors.append(f"{path.name}:{lineno}: NEXT_PUBLIC mit Secret-Muster im Namen: {env_key.strip()}")
        v = val.strip()
        for submsg in _forbidden_secrets_in_line(env_key, v):
            errors.append(
                f"{path.name}:{lineno}: {submsg} — Wert beginnt: {v[:32]!r}…"
            )
    # Demo/Live-Mix als Template-Contract (Namebasierte Heuristik)
    demo_enabled = parsed.get("BITGET_DEMO_ENABLED", "").strip().lower() in {"true", "1", "yes", "on"}
    live_values = [
        parsed.get("BITGET_API_KEY", ""),
        parsed.get("BITGET_API_SECRET", ""),
        parsed.get("BITGET_API_PASSPHRASE", ""),
    ]
    has_real_live = any(v and not _is_allowed_placeholder_value(v) for v in live_values)
    if demo_enabled and has_real_live:
        errors.append(f"{path.name}: Demo/Live-Credential-Mix erkannt (BITGET_DEMO_ENABLED=true + BITGET_API_* gesetzt)")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files_strict: tuple[Path, ...] = (
        tuple(Path(a).resolve() for a in args) if args else _TEMPLATES_STRICT
    )
    files_secret: tuple[Path, ...] = (
        files_strict
        if args
        else _TEMPLATES_SECRET_SCAN
    )

    all_err: list[str] = []
    for p in files_strict:
        all_err.extend(_check_forbidden_flags(p))
    for p in files_secret:
        all_err.extend(_check_secrets_in_templates(p))
    if all_err:
        print("check_production_env_template_security: FAILED", file=sys.stderr)
        print("\n".join(all_err), file=sys.stderr)
        return 1
    print(
        "OK check_production_env_template_security: "
        "Vorlagen ohne verbotene Flags/typische Committed-Secrets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
