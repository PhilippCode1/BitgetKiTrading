#!/usr/bin/env python3
"""
Release-Candidate: Edge-Health ohne published Engine-Ports (nur docker-compose.yml).

Prueft /v1/meta/surface, /v1/deploy/edge-readiness, Gateway /ready (inkl. checks),
Dashboard /api/health, aggregiertes /v1/system/health und Lesepfade
(Paper, Learning inkl. Drift, Monitor, Live-State).

Auth: Wenn das Gateway JWT fuer /v1/* verlangt, setze in der Shell
DASHBOARD_GATEWAY_AUTHORIZATION="Bearer <jwt>" (gleicher Wert wie im Dashboard-Container).
Lokal mit API_AUTH_MODE=none reicht oft ohne Header (siehe .env.local.example).

Exit-Codes: 0 = alles gruen, 1 = degradiert/Timeout. Startup: bis RC_HEALTH_STARTUP_BUDGET_SEC
mit exponentiellen Backoff Retries, damit fluechtige Neustarts (Redis, Gateway) Zeit haben.
--stress: 10 Laeufe im 2s-Abstand; 1, wenn ein Lauf scheitert (Flapping wird in stderr klar benannt).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

STRESS_ROUNDS_DEFAULT = 10
STRESS_INTERVAL_SEC = 2.0
STARTUP_BUDGET_SEC_DEFAULT = 60.0


def _gateway_auth_headers() -> dict[str, str]:
    h: dict[str, str] = {"User-Agent": "rc_health_edge/1.0"}
    auth = (os.environ.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()
    if auth:
        h["Authorization"] = auth
    return h


def _get(
    url: str,
    timeout: float = 12.0,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    merged = {"User-Agent": "rc_health_edge/1.0"}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _json(
    url: str,
    timeout: float = 12.0,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    try:
        code, raw = _get(url, timeout=timeout, headers=headers)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SystemExit(
                f"FAIL {url} -> HTTP {e.code} (setze DASHBOARD_GATEWAY_AUTHORIZATION=Bearer <jwt>)"
            ) from e
        raise SystemExit(f"FAIL {url} -> HTTP {e.code}") from e
    except OSError as e:
        raise SystemExit(f"FAIL {url} -> {e}") from e
    if code != 200:
        raise SystemExit(f"FAIL {url} -> HTTP {code}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"FAIL {url} kein JSON") from e
    if not isinstance(data, dict):
        raise SystemExit(f"FAIL {url} JSON ist kein Objekt")
    return data


def _format_gateway_ready_failures(checks: dict) -> list[str]:
    """API-Gateway liefert checks meist als dict[str, {ok, detail}]."""
    failed: list[str] = []
    for key, value in checks.items():
        if isinstance(value, dict) and value.get("ok") is False:
            detail = str(value.get("detail", "failed"))[:200]
            failed.append(f"{key}: {detail}")
        elif isinstance(value, (list, tuple)) and value and not bool(value[0]):
            detail = value[1] if len(value) > 1 else "failed"
            failed.append(f"{key}:{detail}")
    return failed


def _check_gateway_ready(url: str) -> None:
    p = _json(url)
    if p.get("ready") is not True:
        raise SystemExit(f"FAIL gateway /ready ready!=true payload={p!r}")
    checks = p.get("checks") or {}
    if isinstance(checks, dict):
        failed = _format_gateway_ready_failures(checks)
        if failed:
            raise SystemExit("FAIL gateway /ready checks: " + "; ".join(failed))
    print(f"OK  gateway /ready ({url})")


def _check_dashboard_health(url: str) -> None:
    p = _json(url)
    if str(p.get("status", "")).strip().lower() != "ok":
        raise SystemExit(f"FAIL dashboard /api/health status={p.get('status')!r}")
    if str(p.get("service", "")).strip().lower() != "dashboard":
        raise SystemExit(f"FAIL dashboard /api/health service={p.get('service')!r}")
    print(f"OK  dashboard /api/health ({url})")


def _check_system_health(url: str, *, headers: dict[str, str] | None = None) -> dict:
    health = _json(url, headers=headers)
    if health.get("database") != "ok":
        raise SystemExit(f"FAIL system-health database={health.get('database')!r}")
    if health.get("redis") != "ok":
        raise SystemExit(f"FAIL system-health redis={health.get('redis')!r}")

    required = (
        "market-stream",
        "feature-engine",
        "structure-engine",
        "drawing-engine",
        "signal-engine",
        "news-engine",
        "llm-orchestrator",
        "paper-broker",
        "learning-engine",
        "alert-engine",
        "monitor-engine",
        "live-broker",
    )
    services = {
        s.get("name"): s
        for s in health.get("services") or []
        if isinstance(s, dict) and s.get("name")
    }
    missing = sorted(set(required) - set(services.keys()))
    if missing:
        raise SystemExit(f"FAIL system-health fehlende services: {missing}")
    bad = [n for n in sorted(required) if str(services[n].get("status", "")).strip().lower() != "ok"]
    if bad:
        raise SystemExit(f"FAIL system-health services nicht ok: {bad}")

    ops = health.get("ops")
    if not isinstance(ops, dict):
        raise SystemExit("FAIL system-health ops summary fehlt")
    for key in ("monitor", "alert_engine", "live_broker"):
        if not isinstance(ops.get(key), dict):
            raise SystemExit(f"FAIL system-health ops.{key} fehlt")

    warnings = health.get("warnings") or []
    wtxt = f" warnings={warnings}" if warnings else ""
    mon = int(ops["monitor"].get("open_alert_count") or 0)
    obf = int(ops["alert_engine"].get("outbox_failed") or 0)
    ks = int(ops["live_broker"].get("active_kill_switch_count") or 0)
    print(
        f"OK  system-health ({url}) monitor_open={mon} outbox_failed={obf}"
        f" active_kill_switches={ks}{wtxt}"
    )
    return health


def _check_public_surface(url: str) -> None:
    d = _json(url)
    if d.get("schema_version") != "public-surface-v1":
        raise SystemExit(f"FAIL meta/surface schema_version={d.get('schema_version')!r}")
    for key in ("execution", "commerce", "auth"):
        if key not in d or not isinstance(d[key], dict):
            raise SystemExit(f"FAIL meta/surface fehlt oder kein Objekt: {key}")
    print(f"OK  meta/surface ({url})")


def _check_deploy_edge(url: str) -> None:
    d = _json(url)
    pe = d.get("public_endpoints")
    sh = d.get("security_headers")
    if not isinstance(pe, dict) or not isinstance(sh, dict):
        raise SystemExit("FAIL deploy/edge-readiness: public_endpoints/security_headers fehlen")
    print(f"OK  deploy/edge-readiness ({url})")


def _run_once(gw: str, dash: str) -> None:
    gh = _gateway_auth_headers()
    _check_public_surface(f"{gw}/v1/meta/surface")
    _check_deploy_edge(f"{gw}/v1/deploy/edge-readiness")
    _check_gateway_ready(f"{gw}/ready")
    _check_dashboard_health(f"{dash}/api/health")
    _check_system_health(f"{gw}/v1/system/health", headers=gh)

    for label, path in (
        ("paper-metrics", "/v1/paper/metrics/summary"),
        ("learning-metrics", "/v1/learning/metrics/strategies"),
        ("learning-drift-recent", "/v1/learning/drift/recent"),
        ("learning-drift-online-state", "/v1/learning/drift/online-state"),
        ("monitor-alerts-open", "/v1/monitor/alerts/open"),
        ("live-state", "/v1/live/state?timeframe=1m"),
    ):
        _json(f"{gw}{path}", headers=gh)
        print(f"OK  {label} ({gw}{path})")


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _run_stress(
    gw: str,
    dash: str,
    rounds: int,
    interval_sec: float,
) -> int:
    n_ok = 0
    last_err: str | None = None
    for r in range(1, int(rounds) + 1):
        try:
            _run_once(gw, dash)
        except (SystemExit, OSError) as e:
            last_err = str(e) if e else None
            print(
                f"RETRY/FEHLER rc_health_edge --stress {r}/{rounds}: {e!s}",
                file=sys.stderr,
            )
        except Exception as e:  # pragma: no cover - Sicherheitsnetz
            last_err = str(e)
            print(
                f"RETRY/FEHLER rc_health_edge --stress {r}/{rounds}: {e!s}",
                file=sys.stderr,
            )
        else:
            n_ok += 1
            print(f"OK  rc_health_edge --stress {r}/{rounds}", file=sys.stderr)
        if r < int(rounds):
            time.sleep(max(0.1, float(interval_sec)))
    if n_ok == int(rounds):
        print(
            f"OK  rc_health_edge: --stress {n_ok}/{rounds} alle gruen (stabil).",
            file=sys.stderr,
        )
        return 0
    if 0 < n_ok < int(rounds):
        print(
            f"FEHLER rc_health_edge: --stress FLAPPING/instabil (ok={n_ok}/{rounds}, zuletzt: {last_err!r})",
            file=sys.stderr,
        )
    else:
        print(
            f"FEHLER rc_health_edge: --stress dauerhaft rot (0/{rounds} ok, zuletzt: {last_err!r})",
            file=sys.stderr,
        )
    return 1


def _run_with_startup_backoff(
    gw: str,
    dash: str,
    budget_sec: float,
) -> int:
    t0 = time.time()
    delay = 0.5
    attempt = 0
    last_err: BaseException | None = None
    while time.time() - t0 < float(budget_sec):
        attempt += 1
        try:
            _run_once(gw, dash)
            print(
                "OK  rc_health_edge: alle Pruefungen gruen (warnings in system/health "
                "sind Hinweise, kein Fehler).",
            )
            return 0
        except SystemExit as e:
            last_err = e
        except OSError as e:
            last_err = e
        remain = float(budget_sec) - (time.time() - t0)
        if remain <= 0.1:
            break
        w = min(delay, remain, 8.0)
        print(
            f"RETRY rc_health_edge (startup budget {float(budget_sec):.0f}s) attempt={attempt} "
            f"sleep={w:.2f}s remain={remain:.1f}s err={last_err!s}",
            file=sys.stderr,
        )
        time.sleep(w)
        delay = min(8.0, max(0.5, delay * 1.5))
    _print_smoke_diagnose(gw, dash, last_err or RuntimeError("unbekannter fehler"))
    return 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Edge Release-Candidate Health (Quality Gate).")
    p.add_argument(
        "--stress",
        action="store_true",
        help=(
            f"Stabilitaet: {STRESS_ROUNDS_DEFAULT} volle Durchlaeufe, "
            f"Abstand {STRESS_INTERVAL_SEC:.0f}s; Exit 0 nur wenn alle gruen (Flapping erkennbar in stderr)"
        ),
    )
    p.add_argument(
        "--stress-rounds",
        type=int,
        default=STRESS_ROUNDS_DEFAULT,
        help=f"Anzahl Laeufe fuer --stress (Default {STRESS_ROUNDS_DEFAULT})",
    )
    p.add_argument(
        "--stress-interval-sec",
        type=float,
        default=STRESS_INTERVAL_SEC,
        help="Pause zwischen --stress Laeufen",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    gw = os.environ.get("API_GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/")
    dash = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:3000").rstrip("/")
    if args.stress:
        return _run_stress(
            gw, dash, rounds=int(args.stress_rounds), interval_sec=float(args.stress_interval_sec)
        )
    budget = _env_float("RC_HEALTH_STARTUP_BUDGET_SEC", STARTUP_BUDGET_SEC_DEFAULT)
    return _run_with_startup_backoff(gw, dash, budget)


def _print_smoke_diagnose(gw: str, dash: str, err: BaseException) -> None:
    auth = (os.environ.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()
    print("", file=sys.stderr)
    print("=== SMOKE / rc_health — DIAGNOSE (letzter Fehler) ===", file=sys.stderr)
    print(f"  {err}", file=sys.stderr)
    print("  API_GATEWAY_URL=" + gw, file=sys.stderr)
    print("  DASHBOARD_URL=" + dash, file=sys.stderr)
    if not auth:
        print(
            "  HINWEIS: DASHBOARD_GATEWAY_AUTHORIZATION leer — bei JWT-Pflicht "
            "403/401: Bearer setzen (wie Dashboard-Container), z. B. per mint_dashboard_gateway_jwt.",
            file=sys.stderr,
        )
    else:
        print("  DASHBOARD_GATEWAY_AUTHORIZATION=Bearer *** (gesetzt)", file=sys.stderr)
    print(
        "  Container: docker compose ps | Logs: scripts/dev_logs.ps1 (Windows) / docker compose logs",
        file=sys.stderr,
    )
    print(
        "  Alternativer Gate (curl): bash scripts/healthcheck.sh (ENV URLs wie Compose)",
        file=sys.stderr,
    )
    print("=== Ende DIAGNOSE ===", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
