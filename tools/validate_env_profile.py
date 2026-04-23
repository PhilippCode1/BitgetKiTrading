#!/usr/bin/env python3
"""
Validiert .env-Dateien gegen Profil-Pflichtvariablen (keine <SET_ME> / leer).
Nutzt config/required_secrets_matrix.json plus bedingte Regeln (LLM, Telegram, Live-Trading).
Zusaetzlich: Host-vs.-Container-URL-Konsistenz (config/bootstrap_env_checks.py;
bei profile staging/shadow/production: kein localhost/127.0.0.1/::1 in API_GATEWAY_URL, DASHBOARD_URL, FRONTEND_URL, … (siehe bootstrap_env_checks),
NEXT_PUBLIC_*-Namen ohne Secret-Muster, Gateway->LLM-Basis mindestens eine URL.

Nach JWT-Mint (lokal): erneut mit --with-dashboard-operator aufrufen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config.bootstrap_env_checks import bootstrap_env_consistency_issues
from config.required_secrets import required_env_names_for_env_file_profile

_DOC_BASE = (
    "docs/CONFIGURATION.md | docs/env_profiles.md | "
    "docs/chatgpt_handoff/03_ENV_SECRETS_AUTH_MATRIX.md | "
    "docs/cursor_execution/08_env_profiles_and_secrets_sync.md"
)

# Substrings in NEXT_PUBLIC_*-Schluesseln, die auf Secrets/Server-only hindeuten (niemals im Browser-Prefix).
_FORBIDDEN_NEXT_PUBLIC_SUBSTRINGS: tuple[str, ...] = (
    "OPENAI",
    "BITGET_API",
    "BITGET_DEMO",
    "BITGET_SECRET",
    "GATEWAY_JWT",
    "GATEWAY_INTERNAL",
    "INTERNAL_API",
    "DASHBOARD_GATEWAY",
    "ADMIN_TOKEN",
    "SECRET_KEY",
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "COMMERCIAL_METER",
    "TELEGRAM_BOT",
    "STRIPE_SECRET",
    "PAYMENT_STRIPE_SECRET",
    "PAYMENT_MOCK_WEBHOOK",
)

_ENV_VALUE_HINTS: dict[str, str] = {
    "POSTGRES_PASSWORD": "Ein Passwort fuer Postgres; muss mit DATABASE_URL / DATABASE_URL_DOCKER uebereinstimmen.",
    "DATABASE_URL": "Host-Sicht (localhost). Docker-Worker: DATABASE_URL_DOCKER mit Dienstname postgres.",
    "DATABASE_URL_DOCKER": "Container-Netz: postgresql://...@postgres:5432/... (gleiches Passwort wie POSTGRES_PASSWORD).",
    "REDIS_URL": "Host-Sicht. Compose-Worker: REDIS_URL_DOCKER=redis://redis:6379/0.",
    "REDIS_URL_DOCKER": "Container-Netz redis://redis:6379/0 - nicht 127.0.0.1 fuer andere Container.",
    "JWT_SECRET": "App-weites JWT (nicht Gateway). Siehe docs/SECRETS_MATRIX.md.",
    "SECRET_KEY": "Session/Cookie-Signing u. a. - stark und zufaellig.",
    "ADMIN_TOKEN": "Legacy X-Admin-Token; in Shadow/Prod typisch deaktiviert (GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=false).",
    "ENCRYPTION_KEY": "Feldverschluesselung - Mindestlaenge siehe config/settings.py.",
    "INTERNAL_API_KEY": (
        "Header X-Internal-Service-Key (Dienst-zu-Dienst). Alias SERVICE_INTERNAL_API_KEY. "
        "Gleicher Wert in Gateway und llm-orchestrator/live-broker/... - "
        "nicht verwechseln mit GATEWAY_INTERNAL_API_KEY (X-Gateway-Internal-Key)."
    ),
    "GATEWAY_JWT_SECRET": (
        "HS256 fuer Gateway-JWT. Dashboard-BFF: scripts/mint_dashboard_gateway_jwt.py "
        "--env-file .env.local --update-env-file -> DASHBOARD_GATEWAY_AUTHORIZATION."
    ),
    "API_GATEWAY_URL": (
        "Lokal: http://127.0.0.1:8000. Staging/Production: kein Host-Loopback; "
        "in Container typisch http://api-gateway:8000 oder oeffentliche BFF-URL. "
        "Nicht mit NEXT_PUBLIC_API_BASE_URL (Browser) verwechseln — siehe STAGING_PARITY.md."
    ),
    "NEXT_PUBLIC_API_BASE_URL": "Oeffentliche HTTP-Basis fuer den Browser/Build - keine Secrets, nur http(s) zum Gateway.",
    "NEXT_PUBLIC_WS_BASE_URL": "Oeffentliche WS-Basis (ws:// oder wss://) - keine Secrets.",
    "DASHBOARD_GATEWAY_AUTHORIZATION": (
        "Vollstaendiger Authorization-Header (z. B. Bearer ...), nur Next-Server (BFF). "
        "Lokal optional bis Mint; Shadow/Production laut Matrix required."
    ),
}


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        quoted_double = val.startswith('"') and val.endswith('"')
        quoted_single = val.startswith("'") and val.endswith("'")
        if quoted_double or quoted_single:
            val = val[1:-1]
        out[key] = val
    return out


def _bad(val: str) -> bool:
    t = val.strip()
    if not t:
        return True
    u = t.upper()
    if "<SET_ME>" in u or u == "SET_ME" or u == "CHANGE_ME":
        return True
    return False


def _truthy(val: str) -> bool:
    return val.strip().lower() in ("1", "true", "yes", "on")


def next_public_secret_key_issues(env: dict[str, str]) -> list[str]:
    issues: list[str] = []
    for k in sorted(env):
        if not k.startswith("NEXT_PUBLIC_"):
            continue
        ku = k.upper()
        for frag in _FORBIDDEN_NEXT_PUBLIC_SUBSTRINGS:
            if frag in ku:
                issues.append(
                    f"  {k}: NEXT_PUBLIC_* darf keinen Secret-artigen Namen enthalten ({frag!r}). "
                    "Nur serverseitige ENV ohne NEXT_PUBLIC_-Prefix; siehe 03_ENV_SECRETS_AUTH_MATRIX.md §4."
                )
                break
    return issues


def llm_gateway_base_issues(env: dict[str, str], profile: str) -> list[str]:
    prod_like = profile in ("staging", "shadow", "production")
    if not prod_like:
        return []
    lb = (env.get("LLM_ORCH_BASE_URL") or "").strip()
    hh = (env.get("HEALTH_URL_LLM_ORCHESTRATOR") or "").strip()
    if not _bad(lb) or not _bad(hh):
        return []
    return [
        "  Gateway->LLM: weder LLM_ORCH_BASE_URL noch HEALTH_URL_LLM_ORCHESTRATOR gesetzt (oder beide leer/Platzhalter). "
        "Mindestens eine URL mit echtem Host, z. B. http://llm-orchestrator:8070 bzw. .../ready unter Compose. "
        "Siehe 03_ENV_SECRETS_AUTH_MATRIX.md §5.3."
    ]


def conditional_env_issues(env: dict[str, str], profile: str) -> list[str]:
    """Zusaetzliche Regeln, die von Feature-Flags abhaengen."""
    issues: list[str] = []
    prod_like = profile in ("staging", "shadow", "production")
    production_flag = _truthy(env.get("PRODUCTION", ""))

    llm_fake = env.get("LLM_USE_FAKE_PROVIDER", "true").strip().lower()
    if prod_like or production_flag:
        if _truthy(env.get("LLM_USE_FAKE_PROVIDER", "")):
            issues.append(
                "LLM_USE_FAKE_PROVIDER=true ist fuer PRODUCTION/shadow/staging nicht erlaubt "
                "(echter OpenAI-Pfad im Orchestrator). Siehe config/settings.py und 03_ENV_SECRETS_AUTH_MATRIX.md §2.5."
            )
        if _bad(env.get("OPENAI_API_KEY", "")):
            issues.append(
                "OPENAI_API_KEY fehlt oder ist Platzhalter: Ohne Fake-Provider muss der Key im llm-orchestrator "
                "gesetzt sein (PRODUCTION/shadow/staging). Setze einen echten Provider-Key oder nur lokal "
                "LLM_USE_FAKE_PROVIDER=true. Siehe 03_ENV_SECRETS_AUTH_MATRIX.md §2.5."
            )

    if not prod_like and not production_flag:
        if llm_fake in ("false", "0", "no", "off"):
            if _bad(env.get("OPENAI_API_KEY", "")):
                issues.append(
                    "OPENAI_API_KEY fehlt bei LLM_USE_FAKE_PROVIDER=false (lokal): "
                    "Key setzen oder LLM_USE_FAKE_PROVIDER=true fuer deterministische Antworten."
                )

    if _truthy(env.get("COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE", "")):
        if _bad(env.get("TELEGRAM_BOT_TOKEN", "")):
            issues.append("TELEGRAM_BOT_TOKEN Pflicht wenn COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE=true")

    if _truthy(env.get("LIVE_TRADE_ENABLE", "")) and not _truthy(env.get("BITGET_DEMO_ENABLED", "")):
        for key in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"):
            if _bad(env.get(key, "")):
                issues.append(f"{key} Pflicht wenn LIVE_TRADE_ENABLE=true und kein Demo-Modus")
                break

    if _truthy(env.get("BITGET_ALLOW_DEMO_SCHEMA_SEEDS", "")) and (prod_like or production_flag):
        issues.append(
            "BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true ist fuer shadow/production/staging verboten "
            "(nur lokale optional SQL unter infra/migrations/postgres_demo/). "
            "Siehe docs/cursor_execution/11_migrations_and_seed_separation.md."
        )

    return issues


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, required=True)
    p.add_argument(
        "--profile",
        choices=("local", "staging", "shadow", "production"),
        required=True,
    )
    p.add_argument(
        "--with-dashboard-operator",
        action="store_true",
        help="Erzwingt DASHBOARD_GATEWAY_AUTHORIZATION (nach mint_dashboard_gateway_jwt, nur sinnvoll fuer profile=local).",
    )
    args = p.parse_args()
    if not args.env_file.is_file():
        print(f"FEHLT: {args.env_file}", file=sys.stderr)
        return 1
    fname = args.env_file.name.lower()
    if args.profile == "local" and fname in (".env.production", ".env.shadow", ".env.staging"):
        print(
            "validate_env_profile: Profil 'local' widerspricht dem Dateinamen "
            f"{args.env_file.name} - nutze --profile staging/shadow/production.",
            file=sys.stderr,
        )
        return 1
    if args.profile == "production" and fname in (".env.shadow", ".env.staging"):
        print(
            f"validate_env_profile: Hinweis: {args.env_file.name} ist typisch Pre-Prod - "
            "APP_ENV in der Datei pruefen; bei shadow/staging-Deploy --profile staging verwenden.",
            file=sys.stderr,
        )
    if args.with_dashboard_operator and args.profile != "local":
        print(
            "validate_env_profile: --with-dashboard-operator ist nur fuer --profile local vorgesehen "
            "(Shadow/Prod: DASHBOARD_GATEWAY_AUTHORIZATION steht bereits in der Matrix).",
            file=sys.stderr,
        )

    env = load_dotenv(args.env_file)
    required = required_env_names_for_env_file_profile(
        profile=args.profile,
        with_dashboard_operator=args.with_dashboard_operator,
    )
    problems: list[str] = []
    for key in required:
        val = env.get(key, "")
        if _bad(val):
            hint = _ENV_VALUE_HINTS.get(key, "")
            line = f"  {key}: leer oder Platzhalter"
            if hint:
                line += f" - {hint}"
            problems.append(line)

    problems.extend(f"  {m}" for m in conditional_env_issues(env, args.profile))
    problems.extend(f"  {m}" for m in next_public_secret_key_issues(env))
    problems.extend(llm_gateway_base_issues(env, args.profile))
    problems.extend(bootstrap_env_consistency_issues(env, profile=args.profile))

    if problems:
        msg = f"validate_env_profile: {args.profile} - {args.env_file}"
        print(msg, file=sys.stderr)
        print("Probleme:", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Dokumentation: {_DOC_BASE}", file=sys.stderr)
        return 1
    print(f"OK validate_env_profile: {args.profile} {args.env_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
