#!/usr/bin/env python3
"""
API-Integrations-Smoke (ohne Secrets in stdout): Gateway, JWT-Pfad, optional Bitget oeffentlich.

Laedt .env.local (oder --env-file), prueft Erreichbarkeit und gibt klare Diagnosetexte aus.
Exit 0 wenn alle kritischen Schritte gruen, sonst 1.

Siehe API_INTEGRATION_STATUS.md im Repo-Root.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        out[key] = val
    return out


def http_json(method: str, url: str, *, headers: dict[str, str] | None = None, timeout: float = 12.0) -> tuple[int, object]:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        code = resp.status
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return code, {}
        return code, json.loads(raw)


def http_get_text(url: str, timeout: float = 10.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")[:600]


def warn_internal_forward_wiring(env: dict[str, str]) -> None:
    """
    Keine Secrets ausgeben: nur Hinweise, ob interne Ziele/Schluessel aus der ENV-Datei ableitbar sind.
    (Im Container ueberschreibt compose oft HEALTH_URL_* / Keys — dann ist die Datei allein nicht massgeblich.)
    """
    prod = env.get("PRODUCTION", "").strip().lower() in ("1", "true", "yes")
    int_k = (
        env.get("INTERNAL_API_KEY", "").strip()
        or env.get("SERVICE_INTERNAL_API_KEY", "").strip()
    )
    if prod and not int_k:
        print(
            "[intern] PRODUCTION=true aber weder INTERNAL_API_KEY noch SERVICE_INTERNAL_API_KEY — "
            "Gateway→Orchestrator/live-broker erwartet X-Internal-Service-Key.",
            file=sys.stderr,
        )
    orch = env.get("LLM_ORCH_BASE_URL", "").strip()
    h_orch = env.get("HEALTH_URL_LLM_ORCHESTRATOR", "").strip()
    if not orch and not h_orch:
        print(
            "[intern] Weder LLM_ORCH_BASE_URL noch HEALTH_URL_LLM_ORCHESTRATOR — "
            "LLM-Basis-URL im Gateway nicht aus dieser Datei ableitbar.",
            file=sys.stderr,
        )
    lb = env.get("LIVE_BROKER_BASE_URL", "").strip()
    h_lb = env.get("HEALTH_URL_LIVE_BROKER", "").strip()
    if not lb and not h_lb:
        print(
            "[intern] Weder LIVE_BROKER_BASE_URL noch HEALTH_URL_LIVE_BROKER — "
            "live-broker-Basis-URL im Gateway nicht aus dieser Datei ableitbar.",
            file=sys.stderr,
        )


def warn_docker_health_urls(env: dict[str, str]) -> None:
    """
    Hinweis: .env.local enthaelt oft localhost fuer Host-Tools.
    docker-compose.yml setzt fuer api-gateway typisch explizite http://service:port/ready — dann sind
    diese Dateizeilen im Container irrelevant. Nur wenn du den Gateway **ohne** solche Overrides startest,
    muessen HEALTH_URL_* Docker-Dienstnamen nutzen.
    """
    bad: list[str] = []
    for k, v in sorted(env.items()):
        if not k.startswith("HEALTH_URL_"):
            continue
        low = v.lower()
        if "localhost" in low or "127.0.0.1" in low:
            bad.append(k)
    if bad:
        print(
            "HINWEIS: In der ENV-Datei zeigen HEALTH_URL_* auf localhost/127.0.0.1: "
            + ", ".join(bad)
            + ". Unter docker-compose werden die Werte am api-gateway oft durch service-Umgebungsvariablen "
            "ueberschrieben — pruefe bei Problemen `docker compose config` bzw. Container-ENV, "
            "nicht nur die Datei.",
            file=sys.stderr,
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, default=Path(".env.local"))
    p.add_argument("--skip-bitget-public", action="store_true", help="Keinen oeffentlichen Bitget-REST testen")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    env_path = args.env_file if args.env_file.is_absolute() else root / args.env_file
    env = load_dotenv(env_path)
    if not env_path.is_file():
        print(f"FEHLT: {env_path}", file=sys.stderr)
        return 1

    bind = (env.get("COMPOSE_EDGE_BIND") or "127.0.0.1").strip().strip('"').strip("'")
    if bind in ("0.0.0.0", "[::]", "::"):
        bind = "127.0.0.1"
    gw = (env.get("API_GATEWAY_URL") or f"http://{bind}:8000").rstrip("/")
    auth = (env.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()

    print("=== api_integration_smoke ===")
    print(f"env_file={env_path}")
    print(f"API_GATEWAY_URL={gw}")
    print(f"DASHBOARD_GATEWAY_AUTHORIZATION={'Bearer ***' if auth else '(leer)'}")

    warn_docker_health_urls(env)
    warn_internal_forward_wiring(env)

    failed = False

    # 1) Gateway /health
    try:
        code, body = http_json("GET", f"{gw}/health", timeout=8.0)
        ok = code == 200 and isinstance(body, dict)
        print(f"[1] GET /health -> HTTP {code} ok={ok}")
        if not ok:
            failed = True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"[1] GET /health -> FAIL {e}", file=sys.stderr)
        failed = True

    # 2) Gateway /ready
    try:
        code, body = http_json("GET", f"{gw}/ready", timeout=12.0)
        ready = isinstance(body, dict) and body.get("ready") is True
        print(f"[2] GET /ready -> HTTP {code} ready={ready}")
        if not ready:
            failed = True
            if isinstance(body, dict) and body.get("checks"):
                print(f"    checks={json.dumps(body.get('checks'), ensure_ascii=False)[:500]}")
        if isinstance(body, dict) and isinstance(body.get("checks"), dict):
            pgs = body["checks"].get("postgres_schema")
            if isinstance(pgs, dict):
                ps_ok = pgs.get("ok")
                det = str(pgs.get("detail") or "")[:220]
                print(f"[2b] postgres_schema ok={ps_ok} detail={det}")
                if ps_ok is False:
                    failed = True
                    print(
                        "    FEHLER: Kern-Schema oder Migrationen unvollstaendig — "
                        "`python infra/migrate.py` (DATABASE_URL) ausfuehren.",
                        file=sys.stderr,
                    )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"[2] GET /ready -> FAIL {e}", file=sys.stderr)
        failed = True

    # 3) JWT system health
    if auth:
        try:
            code, body = http_json(
                "GET",
                f"{gw}/v1/system/health",
                headers={"Authorization": auth},
                timeout=15.0,
            )
            db_ok = isinstance(body, dict) and body.get("database") == "ok"
            redis_ok = isinstance(body, dict) and body.get("redis") == "ok"
            ds = body.get("database_schema") if isinstance(body, dict) else None
            ds_st = ds.get("status") if isinstance(ds, dict) else None
            print(
                f"[3] GET /v1/system/health (JWT) -> HTTP {code} "
                f"database={body.get('database') if isinstance(body, dict) else '?'} "
                f"redis={body.get('redis') if isinstance(body, dict) else '?'} "
                f"database_schema.status={ds_st!r}"
            )
            if code != 200 or not db_ok or not redis_ok:
                failed = True
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")[:400] if e.fp else ""
            print(f"[3] GET /v1/system/health -> HTTP {e.code} {raw}", file=sys.stderr)
            failed = True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"[3] GET /v1/system/health -> FAIL {e}", file=sys.stderr)
            failed = True
    else:
        print("[3] GET /v1/system/health -> SKIP (kein DASHBOARD_GATEWAY_AUTHORIZATION)")
        print("    Mint: python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file", file=sys.stderr)

    # 4) Bitget oeffentlich (Rate-Limits moeglich)
    if not args.skip_bitget_public:
        base_rest = (env.get("BITGET_API_BASE_URL") or "https://api.bitget.com").rstrip("/")
        url = f"{base_rest}/api/v2/spot/market/tickers?symbol=BTCUSDT"
        try:
            code, txt = http_get_text(url, timeout=10.0)
            j = json.loads(txt) if txt.strip().startswith("{") else {}
            ok = code == 200 and str(j.get("code", "")).strip() == "00000"
            print(f"[4] Bitget public tickers -> HTTP {code} api_code={j.get('code', 'n/a')}")
            if not ok:
                print(f"    Hinweis: extern (Netz/Geo/Rate-Limit) — kein sicherer Repo-Defekt. Snip={txt[:200]}", file=sys.stderr)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"[4] Bitget public -> SKIP/FAIL {e} (Netzwerk/Firewall)", file=sys.stderr)

    if failed:
        print("\nERGEBNIS: mindestens ein kritischer Schritt fehlgeschlagen.", file=sys.stderr)
        print("Doku: API_INTEGRATION_STATUS.md | Stack: pnpm dev:up | Diagnose: /api/dashboard/edge-status", file=sys.stderr)
        return 1
    print("\nERGEBNIS: kritische Integrationen (Gateway + optional JWT) OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
