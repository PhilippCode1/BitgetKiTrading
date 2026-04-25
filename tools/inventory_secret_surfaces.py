#!/usr/bin/env python3
"""
Inventar: welche ENV-Schluessel sind Secret, oeffentlich (NEXT_PUBLIC_*), nur Dashboard-Server,
nur Backend — abgeleitet aus config/required_secrets_matrix.json und
apps/dashboard/public-env-allowlist.cjs.

Liefert konsolenlesbare Tabelle und optional --report-md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config" / "required_secrets_matrix.json"
PUBLIC_ALLOW = ROOT / "apps" / "dashboard" / "public-env-allowlist.cjs"

# Wird in server-env.ts, Route-Handlern, Edge gelesen — nie als NEXT_PUBLIC_ duplizieren.
DASHBOARD_SERVER_ONLY: frozenset[str] = frozenset(
    {
        "API_GATEWAY_URL",
        "DASHBOARD_GATEWAY_AUTHORIZATION",
        "PAYMENT_MOCK_WEBHOOK_SECRET",
        "COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE",
    }
)

# Aus docs/SECRETS_MATRIX: kritisch, aber ggf. nicht in der knappen required_secrets_matrix-Union.
ADDITIONAL_CRITICAL_ENV: tuple[dict[str, str], ...] = (
    {
        "env": "BITGET_API_KEY",
        "services": "live-broker, market-stream, …",
        "local": "optional (Demo)",
        "staging": "required (live data)",
        "production": "required for live",
        "surface": "server_backend",
    },
    {
        "env": "BITGET_API_SECRET",
        "services": "live-broker, …",
        "local": "optional (Demo)",
        "staging": "required",
        "production": "required for live",
        "surface": "server_backend",
    },
    {
        "env": "BITGET_API_PASSPHRASE",
        "services": "live-broker, …",
        "local": "optional (Demo)",
        "staging": "required",
        "production": "required for live",
        "surface": "server_backend",
    },
    {
        "env": "TELEGRAM_BOT_TOKEN",
        "services": "alert path",
        "local": "optional",
        "staging": "required if alerts live",
        "production": "required if outbox live",
        "surface": "server_backend",
    },
    {
        "env": "OPENAI_API_KEY",
        "services": "llm-orchestrator, …",
        "local": "optional if fake",
        "staging": "required if not fake",
        "production": "required if not fake",
        "surface": "server_backend",
    },
)


def _read_next_public_keys() -> list[str]:
    raw = PUBLIC_ALLOW.read_text(encoding="utf-8")
    m = re.findall(r'"((?:NEXT_PUBLIC_[A-Z0-9_]+))"', raw)
    return sorted({k for k in m if k.startswith("NEXT_PUBLIC_")})


def _load_matrix() -> list[dict[str, object]]:
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    return list(data.get("entries") or [])


@dataclass(frozen=True, slots=True)
class Row:
    env: str
    kind: str
    surface: str
    public_in_browser: str
    may_placeholder_in_git: str
    services: str
    local: str
    staging: str
    production: str


def _classify_surface(
    env: str,
    next_public: set[str],
) -> tuple[str, str]:
    """
    Returns (surface, public_in_browser_yn).
    surface: browser_public | server_dashboard | server_backend
    """
    if env.startswith("NEXT_PUBLIC_") or env in next_public:
        return "browser_public", "yes (flags/URLs, not secrets by design)"
    if env in DASHBOARD_SERVER_ONLY:
        return "server_dashboard (Next server only)", "no (server components / BFF)"
    return "server_backend (Python/Workers)", "no"


def _placeholder_rule(env: str) -> str:
    if env.startswith("NEXT_PUBLIC_"):
        return "yes: URL/Flags as example only; must be non-loopback in prod"
    return "no: use Vault/SM, never real values in template"


def _classify_kind(env: str, surface: str) -> str:
    u = env.upper()
    if surface.startswith("browser_public"):
        if re.search(r"(SECRET|TOKEN|PASSWORD|PASSPHRASE|PRIVATE|JWT|API_KEY)", u):
            return "public_leak_risk"
        return "public_config"
    if re.search(r"(SECRET|TOKEN|PASSWORD|PASSPHRASE|PRIVATE|JWT|API_KEY|WEBHOOK)", u):
        return "secret"
    return "server_config"


def build_rows() -> list[Row]:
    nxs = set(_read_next_public_keys())
    out_by_env: dict[str, Row] = {}
    for e in _load_matrix():
        env = str(e["env"])
        svc = e.get("services", "*")
        ssvc = json.dumps(svc) if isinstance(svc, (list, dict)) else (str(svc) if svc else "*")
        surf, pub = _classify_surface(env, nxs)
        out_by_env[env] = Row(
            env=env,
            kind=_classify_kind(env, surf),
            surface=surf,
            public_in_browser=pub,
            may_placeholder_in_git=_placeholder_rule(env),
            services=ssvc,
            local=str(e.get("local", "")),
            staging=str(e.get("staging", "")),
            production=str(e.get("production", "")),
        )
    for a in ADDITIONAL_CRITICAL_ENV:
        env = a["env"]
        if env in out_by_env:
            continue
        surf, pub = _classify_surface(env, nxs)
        if "surface" in a:
            surf = a["surface"]
        out_by_env[env] = Row(
            env=env,
            kind=_classify_kind(env, surf),
            surface=surf,
            public_in_browser=pub,
            may_placeholder_in_git="no: production-blocking if leaked",
            services=a["services"],
            local=a["local"],
            staging=a["staging"],
            production=a["production"],
        )
    return sorted(out_by_env.values(), key=lambda r: r.env)


def _md_table(rows: list[Row]) -> str:
    h = (
        "| ENV | Typ | Surface | Public im Browser? | Placeholder in Git-Template? | services | local | staging | production |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    body = "\n".join(
        f"| `{r.env}` | {r.kind} | {r.surface} | {r.public_in_browser} | {r.may_placeholder_in_git} | {r.services} | {r.local} | {r.staging} | {r.production} |"
        for r in rows
    )
    return h + body + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inventar Secret-Surfaces (keine Secret-Werte)."
    )
    ap.add_argument(
        "--report-md",
        metavar="PATH",
        type=Path,
        help="Markdown-Report in diese Datei schreiben (utf-8).",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Zusaetzlich JSON (Zeilen) auf stdout.",
    )
    args = ap.parse_args()
    if not MATRIX.is_file():
        print("Fehlend: config/required_secrets_matrix.json", file=sys.stderr)
        return 2
    rows = build_rows()
    n = len(rows)
    print(
        f"inventoried_secret_surface_rows={n} "
        f"(matrix + {len(ADDITIONAL_CRITICAL_ENV)} zusaetzliche kritische Bitget/Provider-ENV aus Doku) sources={MATRIX.name} + {PUBLIC_ALLOW.name}",
    )
    if args.json:
        out = [asdict(r) for r in rows]
        print(json.dumps({"generated": datetime.now(UTC).isoformat(), "rows": out}, indent=2))
    for r in rows:
        print(
            f"{r.env:45} {r.surface:28} {r.production:10}",
        )
    if args.report_md is not None:
        header = (
            f"# Secret-Surface-Inventar (automatisch)\n\n"
            f"**Generiert:** `{datetime.now(UTC).isoformat()}`\n"
            f"**Quelle:** `config/required_secrets_matrix.json` + `apps/dashboard/public-env-allowlist.cjs` + Ergänzungen in `tools/inventory_secret_surfaces.py` (Bitget/Telegram/LLM).\n\n"
            f"**Anzahl Zeilen:** {n}\n\n"
        )
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(
            header
            + "## Tabelle\n\n"
            + _md_table(rows)
            + "\n## Hinweise\n\n"
            + "- `browser_public` inline’t nur unkritische Konfiguration; trotzdem in Prod bewusst setzen (kein stiller `localhost` im Production-Build).\n"
            + "- `server_dashboard` bleibt in `server-env.ts` / BFF, nie `NEXT_PUBLIC_*`.\n"
            + "- `server_backend` sind Exchange-Keys, interne API-Keys, DB-Passwörter — ausschließlich Laufzeit-Secret-Store, Rotation: `docs/SECRETS_MATRIX.md` (Abschnitt Rotation).\n"
            + "\n**Verifikation (Prod):** `python tools/verify_production_secret_sources.py --env-file <file> --strict`.\n",
            encoding="utf-8",
        )
        print(f"Wrote {args.report_md.as_posix()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
