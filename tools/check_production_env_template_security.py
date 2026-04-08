#!/usr/bin/env python3
"""
CI-Gate: Prod-/Shadow-ENV-Vorlagen ohne aktive gefaehrliche Security-Flags.

Prueft .env.production.example und .env.shadow.example auf verbotene
Zuweisungen (z. B. DEBUG=true, API_AUTH_MODE=none), ohne Kommentarzeilen.
"""

from __future__ import annotations

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

_TEMPLATES: tuple[Path, ...] = (
    ROOT / ".env.production.example",
    ROOT / ".env.shadow.example",
)


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _check_file(path: Path) -> list[str]:
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
                    "(in Prod/Shadow-Vorlage verboten)"
                )
                errors.append(msg)
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    paths: tuple[Path, ...] = (
        tuple(Path(a).resolve() for a in args) if args else _TEMPLATES
    )
    all_err: list[str] = []
    for p in paths:
        all_err.extend(_check_file(p))
    if all_err:
        print("check_production_env_template_security: FAILED", file=sys.stderr)
        print("\n".join(all_err), file=sys.stderr)
        return 1
    print(
        "OK check_production_env_template_security: "
        "keine verbotenen Security-Flags in Vorlagen."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
