#!/usr/bin/env python3
"""
Release-Candidate: Edge-Health ohne published Engine-Ports (nur docker-compose.yml).

Prueft /v1/meta/surface, /v1/deploy/edge-readiness, Gateway /ready (inkl. checks),
Dashboard /api/health, aggregiertes /v1/system/health und Lesepfade
(Paper, Learning inkl. Drift, Monitor, Live-State).

Startup: bis zu RC_HEALTH_STARTUP_BUDGET_SEC (Default 120s, konfigurierbar) mit
Retry bis alle 12+ Integrations-Services in system/health „ok" sind.
--stable-window-sec: nach erstem vollen Gruen: X Sekunden lang durchgehend
ohne Fehler (gegen Flapping/False-Negatives waehrend Boot).
--stress: wie zuvor (nicht mit --stable-window-sec kombinierbar).

Auth: DASHBOARD_GATEWAY_AUTHORIZATION="Bearer <jwt>" wenn /v1/* einen Header braucht.

Bei Exit 1: exakt eine Zeile FEHLER service_id=... service_name=... (siehe stderr / Markdown).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, UTC
from pathlib import Path
from typing import NoReturn

# scripts/ als Modul-Pfad (rc_health_types)
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from rc_health_types import (  # noqa: E402
    RcHealthFailure,
    classify_connection_refused_oserror,
    format_exit_one_line,
)

STRESS_ROUNDS_DEFAULT = 10
STRESS_INTERVAL_SEC = 2.0
STARTUP_BUDGET_SEC_DEFAULT = 120.0

REQUIRED_INTEGRATION_SERVICES: tuple[str, ...] = (
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
# 12 + Meta-/Kernpfade in _run_once => 17+ sichtbare Checks/IDs


def _fail(service_id: str, service_name: str, message: str, *, hint: str = "") -> NoReturn:
    raise RcHealthFailure(service_id, service_name, message, hint=hint)


def _gateway_auth_headers() -> dict[str, str]:
    h: dict[str, str] = {"User-Agent": "rc_health_edge/1.0"}
    auth = (os.environ.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()
    if auth:
        h["Authorization"] = auth
    return h


def _get(
    url: str,
    service_id: str,
    service_name: str,
    timeout: float = 12.0,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    merged = {"User-Agent": "rc_health_edge/1.0"}
    if headers:
        merged.update(headers)
    try:
        req = urllib.request.Request(url, headers=merged)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        raise
    except OSError as e:
        detail = classify_connection_refused_oserror(e)
        _fail(service_id, service_name, detail, hint="network_tcp")


def _json(
    url: str,
    service_id: str,
    service_name: str,
    timeout: float = 12.0,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    try:
        code, raw = _get(url, service_id, service_name, timeout=timeout, headers=headers)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            _fail(
                service_id,
                service_name,
                f"HTTP {e.code} (setze DASHBOARD_GATEWAY_AUTHORIZATION=Bearer <jwt>)" + f" url={url}",
            )
        _fail(service_id, service_name, f"HTTP {e.code} url={url}")
    if code != 200:
        _fail(service_id, service_name, f"HTTP {code} url={url}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        _fail(service_id, service_name, f"kein gueltiges JSON: {e} url={url}")
    if not isinstance(data, dict):
        _fail(service_id, service_name, f"JSON ist kein Objekt url={url}")
    return data


def _format_gateway_ready_failures(checks: dict) -> list[str]:
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
    p = _json(url, "gateway-ready", "API-Gateway /ready")
    if p.get("ready") is not True:
        _fail("gateway-ready", "API-Gateway /ready", f"ready!=true payload={p!r}")
    checks = p.get("checks") or {}
    if isinstance(checks, dict):
        failed = _format_gateway_ready_failures(checks)
        if failed:
            _fail("gateway-ready", "API-Gateway /ready", "checks: " + "; ".join(failed))
    print(f"OK  gateway /ready ({url})")


def _check_dashboard_health(url: str) -> None:
    p = _json(url, "dashboard-api-health", "Dashboard /api/health")
    if str(p.get("status", "")).strip().lower() != "ok":
        _fail(
            "dashboard-api-health",
            "Dashboard /api/health",
            f"status={p.get('status')!r}",
        )
    if str(p.get("service", "")).strip().lower() != "dashboard":
        _fail(
            "dashboard-api-health",
            "Dashboard /api/health",
            f"service={p.get('service')!r}",
        )
    print(f"OK  dashboard /api/health ({url})")


def _check_system_health(url: str, *, headers: dict[str, str] | None = None) -> dict:
    health = _json(
        url,
        "system-health-aggregate",
        "GET /v1/system/health",
        headers=headers,
    )
    if health.get("database") != "ok":
        _fail(
            "system-health-aggregate",
            "GET /v1/system/health",
            f"database={health.get('database')!r}",
        )
    if health.get("redis") != "ok":
        _fail(
            "system-health-aggregate",
            "GET /v1/system/health",
            f"redis={health.get('redis')!r}",
        )

    services = {
        s.get("name"): s
        for s in health.get("services") or []
        if isinstance(s, dict) and s.get("name")
    }
    missing = sorted(set(REQUIRED_INTEGRATION_SERVICES) - set(services.keys()))
    if missing:
        _fail(
            "system-health-services-missing",
            "Integrations-Services in system/health",
            f"fehlend: {missing} (siehe 12+ engines im Dossier)",
        )
    for n in sorted(REQUIRED_INTEGRATION_SERVICES):
        sid = f"syshealth:{n}"
        st = str(services[n].get("status", "")).strip().lower()
        if st != "ok":
            _fail(
                sid,
                f"Integration `{n}`",
                f"status={services[n].get('status')!r} (erwartet ok); payload_excerpt={str(services[n])[:500]}",
            )

    ops = health.get("ops")
    if not isinstance(ops, dict):
        _fail("system-health-ops", "GET /v1/system/health ops", "ops summary fehlt")
    for key in ("monitor", "alert_engine", "live_broker"):
        if not isinstance(ops.get(key), dict):
            _fail(
                "system-health-ops",
                f"ops.{key}",
                "fehlt oder kein Objekt",
            )

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
    d = _json(url, "meta-surface", "GET /v1/meta/surface")
    if d.get("schema_version") != "public-surface-v1":
        _fail(
            "meta-surface",
            "GET /v1/meta/surface",
            f"schema_version={d.get('schema_version')!r}",
        )
    for key in ("execution", "commerce", "auth"):
        if key not in d or not isinstance(d[key], dict):
            _fail("meta-surface", f"/v1/meta/surface {key}", "fehlt oder kein Objekt")
    print(f"OK  meta/surface ({url})")


def _check_deploy_edge(url: str) -> None:
    d = _json(url, "edge-readiness", "GET /v1/deploy/edge-readiness")
    pe = d.get("public_endpoints")
    sh = d.get("security_headers")
    if not isinstance(pe, dict) or not isinstance(sh, dict):
        _fail("edge-readiness", "edge-readiness", "public_endpoints/security_headers fehlen")
    print(f"OK  deploy/edge-readiness ({url})")


def _run_once(gw: str, dash: str) -> None:
    """Alle Pflicht- und Lesepfade (17+ sichtbare Checks inkl. 12 Engines)."""
    gh = _gateway_auth_headers()
    _check_public_surface(f"{gw}/v1/meta/surface")
    _check_deploy_edge(f"{gw}/v1/deploy/edge-readiness")
    _check_gateway_ready(f"{gw}/ready")
    _check_dashboard_health(f"{dash}/api/health")
    _check_system_health(f"{gw}/v1/system/health", headers=gh)

    for check_id, label, path in (
        ("read-paper-metrics", "paper-metrics", "/v1/paper/metrics/summary"),
        ("read-learning-strategies", "learning-metrics", "/v1/learning/metrics/strategies"),
        ("read-drift-recent", "learning-drift-recent", "/v1/learning/drift/recent"),
        ("read-drift-online", "learning-drift-online-state", "/v1/learning/drift/online-state"),
        ("read-monitor-alerts", "monitor-alerts-open", "/v1/monitor/alerts/open"),
        ("read-live-state", "live-state", "/v1/live/state?timeframe=1m"),
    ):
        _json(
            f"{gw}{path}",
            check_id,
            f"Gateway {label}",
            headers=gh,
        )
        print(f"OK  {label} ({gw}{path})")


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_sec_token(raw: str | None) -> float:
    if raw is None or not str(raw).strip():
        return 0.0
    s = str(raw).strip().lower()
    m = re.match(r"^([0-9.]+)\s*([smh])?$", s)
    if not m:
        return float(s)
    n = float(m.group(1))
    u = m.group(2) or "s"
    if u == "s":
        return n
    if u == "m":
        return n * 60.0
    return n * 3600.0


def _print_markdown_summary(
    *,
    ok: bool,
    t_start: float,
    t_end: float,
    budget_sec: float,
    stable_window_sec: float,
    stress: bool,
    failure: RcHealthFailure | None,
) -> None:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    dur = max(0.0, t_end - t_start)
    lines: list[str] = [
        "",
        "<!-- rc:health / rc_health_edge — Zusammenfassung (nach AUDIT_REPORT.md kopieren) -->",
        "",
        f"## rc:health (Quality Gate) – {ts}",
        "",
        f"- **Status**: {'**OK**' if ok else '**FAIL**'}",
        f"- **Laufzeit (s)**: {dur:.1f}",
        f"- **Startup-Budget (RC_HEALTH_STARTUP_BUDGET_SEC / --startup-budget-sec)**: {budget_sec:.0f}",
        f"- **Stable-Window (s)**: {stable_window_sec:.0f}" if stable_window_sec else "- **Stable-Window (s)**: _aus_",
        f"- **Stress-Modus**: {'ja' if stress else 'nein'}",
        f"- **Anzahl vorgesehene Integrations-Services (system/health)**: {len(REQUIRED_INTEGRATION_SERVICES)} + Gateway/Dashboard/Metadaten/Lesepfade = **17+ Prüfpunkte** im Lauf",
        "",
    ]
    if failure:
        lines.extend(
            [
                "- **Fehlgeschlagener Check (für CI)**:",
                f"  - `service_id`: `{failure.service_id}`",
                f"  - `service_name`: {failure.service_name!s}",
                f"  - `message`: {failure.message}",
            ]
        )
        if failure.hint:
            lines.append(f"  - `hint`: {failure.hint}")
        lines.append("")
    lines.append("```")
    lines.append("# Einzeiler (Exit 1):")
    if failure:
        lines.append(format_exit_one_line(failure))
    else:
        lines.append("—")
    lines.append("```")
    print("\n".join(lines))


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
        "  WinError 10061 (connection refused) auf :8000: s.o. 'Diagnose' im Fehltext — entweder "
        "kein Prozess am Port (Container down / compose nicht up) ODER App in Container bootet "
        "noch; Startup-Budget erhoehen/compose healthcheck pruefen.",
        file=sys.stderr,
    )
    print(
        "  Container: docker compose ps | Logs: scripts/dev_logs.ps1 (Windows) / docker compose logs",
        file=sys.stderr,
    )
    print("=== Ende DIAGNOSE ===", file=sys.stderr)


def _run_stable_window(gw: str, dash: str, total_sec: float) -> None:
    """Durchgehend gruen: Wandzeit total_sec, mindestens alle 0,5s ein vollstaendiger _run_once."""
    t_end = time.time() + float(total_sec)
    n = 0
    while time.time() < t_end:
        n += 1
        _run_once(gw, dash)
        rem = t_end - time.time()
        if rem > 0:
            time.sleep(min(0.5, rem))
    print(
        f"OK  rc_health_edge: stable-window {float(total_sec):.0f}s Wandzeit: {n} erfolgreiche Voll-Checks in Folge.",
    )


def _run_with_startup_backoff(
    gw: str,
    dash: str,
    budget_sec: float,
) -> RcHealthFailure | None:
    t0 = time.time()
    delay = 0.5
    attempt = 0
    last_f: RcHealthFailure | None = None
    while time.time() - t0 < float(budget_sec):
        attempt += 1
        try:
            _run_once(gw, dash)
            return None
        except RcHealthFailure as f:
            last_f = f
        remain = float(budget_sec) - (time.time() - t0)
        if remain <= 0.1:
            break
        w = min(delay, remain, 8.0)
        el = format_exit_one_line(last_f) if last_f else ""
        print(
            f"RETRY rc_health_edge (startup budget {float(budget_sec):.0f}s) attempt={attempt} "
            f"sleep={w:.2f}s remain={remain:.1f}s {el}",
            file=sys.stderr,
        )
        time.sleep(w)
        delay = min(8.0, max(0.5, delay * 1.3))
    return last_f


def _run_stress(
    gw: str,
    dash: str,
    rounds: int,
    interval_sec: float,
) -> tuple[int, RcHealthFailure | None]:
    n_ok = 0
    last_f: RcHealthFailure | None = None
    for r in range(1, int(rounds) + 1):
        try:
            _run_once(gw, dash)
        except RcHealthFailure as f:
            last_f = f
            print(
                f"RETRY/FEHLER rc_health_edge --stress {r}/{rounds}: {format_exit_one_line(f)}",
                file=sys.stderr,
            )
        except Exception as e:  # pragma: no cover
            x = RcHealthFailure("stress", "unbekannt", str(e)[:500])
            last_f = x
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
        return 0, None
    if 0 < n_ok < int(rounds) and last_f is not None:
        print(
            f"FEHLER rc_health_edge: --stress FLAPPING/instabil (ok={n_ok}/{rounds}) zuletzt: "
            f"{format_exit_one_line(last_f)}",
            file=sys.stderr,
        )
    elif last_f is not None:
        print(
            f"FEHLER rc_health_edge: --stress dauerhaft rot (0/{rounds} ok) zuletzt: "
            f"{format_exit_one_line(last_f)}",
            file=sys.stderr,
        )
    return 1, last_f


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Edge Release-Candidate Health (Quality Gate).")
    p.add_argument(
        "--stress",
        action="store_true",
        help=(
            f"Stabilitaet: {STRESS_ROUNDS_DEFAULT} volle Durchlaeufe, "
            f"Abstand {STRESS_INTERVAL_SEC:.0f}s; nicht mit --stable-window-sec kombinieren."
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
    p.add_argument(
        "--startup-budget-sec",
        type=float,
        default=None,
        help=(
            f"Warte/Retry-Budget (Default {STARTUP_BUDGET_SEC_DEFAULT}, ENV RC_HEALTH_STARTUP_BUDGET_SEC) "
            "bis alles gruen."
        ),
    )
    p.add_argument(
        "--stable-window-sec",
        type=str,
        default="",
        help="Nach erstem vollen Gruen: z.B. 10 oder 10s – konstant gruen in diesem Fenster (anti-Flap). 0=aus. ENV: RC_HEALTH_STABLE_WINDOW_SEC",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    gw = os.environ.get("API_GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/")
    dash = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:3000").rstrip("/")

    env_stable = (os.environ.get("RC_HEALTH_STABLE_WINDOW_SEC") or "").strip()
    stable_tok = str(args.stable_window_sec or "").strip() or env_stable
    stable_window_sec = _parse_sec_token(stable_tok) if stable_tok else 0.0
    if args.stress and stable_window_sec > 0:
        print("FEHLER: --stress und --stable-window-sec schliessen sich aus.", file=sys.stderr)
        return 1

    budget = (
        float(args.startup_budget_sec)
        if args.startup_budget_sec is not None
        else _env_float("RC_HEALTH_STARTUP_BUDGET_SEC", STARTUP_BUDGET_SEC_DEFAULT)
    )
    t_start = time.time()
    failure: RcHealthFailure | None = None

    if args.stress:
        rc, failure = _run_stress(
            gw, dash, rounds=int(args.stress_rounds), interval_sec=float(args.stress_interval_sec)
        )
        _print_markdown_summary(
            ok=rc == 0,
            t_start=t_start,
            t_end=time.time(),
            budget_sec=budget,
            stable_window_sec=0.0,
            stress=True,
            failure=failure,
        )
        if failure and rc != 0:
            print(format_exit_one_line(failure), file=sys.stderr)
        return rc

    f_err = _run_with_startup_backoff(gw, dash, budget)
    if f_err is not None:
        print(format_exit_one_line(f_err), file=sys.stderr)
        _print_smoke_diagnose(gw, dash, f_err)
        _print_markdown_summary(
            ok=False,
            t_start=t_start,
            t_end=time.time(),
            budget_sec=budget,
            stable_window_sec=stable_window_sec,
            stress=False,
            failure=f_err,
        )
        return 1

    try:
        if stable_window_sec > 0.0:
            _run_stable_window(gw, dash, stable_window_sec)
    except RcHealthFailure as f:
        failure = f
        print(format_exit_one_line(f), file=sys.stderr)
        _print_markdown_summary(
            ok=False,
            t_start=t_start,
            t_end=time.time(),
            budget_sec=budget,
            stable_window_sec=stable_window_sec,
            stress=False,
            failure=failure,
        )
        return 1

    print(
        "OK  rc_health_edge: alle Pruefungen gruen (warnings in system/health sind Hinweise, kein Fehler).",
    )
    _print_markdown_summary(
        ok=True,
        t_start=t_start,
        t_end=time.time(),
        budget_sec=budget,
        stable_window_sec=stable_window_sec,
        stress=False,
        failure=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
