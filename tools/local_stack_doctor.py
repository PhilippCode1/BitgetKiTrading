#!/usr/bin/env python3
"""
Lokaler Diagnose-Lauf: ENV (.env.local), Host-vs-Container-URLs, Gateway /health /ready,
Dashboard-JWT (Vorhandensein, optional Ablauf).

Keine Secrets ausgeben. Aus Repo-Root:
  python tools/local_stack_doctor.py
  python tools/local_stack_doctor.py --env-file .env.local
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        out[key] = val
    return out


def _http_get(url: str, *, timeout_sec: float) -> tuple[int | None, str]:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "local-stack-doctor/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read(1200).decode("utf-8", errors="replace")
            return int(resp.status), body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(800).decode("utf-8", errors="replace")
        except OSError:
            body = str(e)
        return int(e.code), body
    except Exception as exc:  # noqa: BLE001 — CLI-Diagnose
        return None, str(exc)


def _docker_internal_host(hostname: str) -> bool:
    h = (hostname or "").strip().lower()
    if h in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        return False
    if re.match(r"^[\d.]+$", h):
        return False
    # typische Compose-Service-Namen
    return "." not in h or h.endswith(".internal")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", type=Path, default=_REPO_ROOT / ".env.local")
    ap.add_argument(
        "--json", action="store_true", help="Maschinenlesbare Ausgabe auf stdout"
    )
    ap.add_argument("--timeout", type=float, default=6.0, help="HTTP-Timeout Sekunden")
    args = ap.parse_args()

    env_path = (
        args.env_file if args.env_file.is_absolute() else _REPO_ROOT / args.env_file
    )
    report: dict[str, Any] = {
        "env_file": str(env_path),
        "checks": [],
        "exit_hint": None,
    }
    critical = False

    def add_check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        nonlocal critical
        if not ok:
            critical = True

    if not env_path.is_file():
        add_check("env_file", False, f"Datei fehlt: {env_path}")
        report["exit_hint"] = (
            "Kopiere .env.local.example nach .env.local (siehe docs/LOCAL_START_MINIMUM.md)."
        )
        if args.json:
            print(json.dumps({**report, "ok": False}, indent=2))
        else:
            print(f"FAIL: {report['exit_hint']}")
        return 1

    env = _load_dotenv(env_path)
    secret = (env.get("GATEWAY_JWT_SECRET") or "").strip()
    gw_url = (env.get("API_GATEWAY_URL") or "").strip().rstrip("/")
    auth_raw = (env.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()
    llm_url = (
        env.get("LLM_ORCH_BASE_URL") or env.get("HEALTH_URL_LLM_ORCHESTRATOR") or ""
    ).strip()

    if not secret:
        add_check(
            "GATEWAY_JWT_SECRET",
            False,
            "Leer — fuer Mint und Gateway muss gesetzt sein.",
        )
    else:
        add_check(
            "GATEWAY_JWT_SECRET", True, "Gesetzt (Laenge ok, Wert nicht ausgegeben)."
        )

    if not gw_url:
        add_check(
            "API_GATEWAY_URL", False, "Leer — Next.js-Server braucht URL zum Gateway."
        )
    else:
        parsed = urlparse(gw_url)
        host_warn = ""
        if parsed.hostname and _docker_internal_host(parsed.hostname):
            host_warn = (
                f" Hostname '{parsed.hostname}' ist typisch nur im Docker-Netz erreichbar. "
                "Auf dem Windows-/Mac-Host oft http://127.0.0.1:8000 nutzen (siehe .env.local.example)."
            )
        add_check("API_GATEWAY_URL", True, f"{gw_url}{host_warn}")

    if (
        not auth_raw
        or auth_raw.upper().startswith("BEARER <")
        or "SET_ME" in auth_raw.upper()
    ):
        add_check(
            "DASHBOARD_GATEWAY_AUTHORIZATION",
            False,
            "Fehlt oder Platzhalter — Operator-Health liefert 503 bis Mint.",
        )
    else:
        add_check(
            "DASHBOARD_GATEWAY_AUTHORIZATION",
            True,
            "Gesetzt (Bearer …, Token nicht ausgegeben).",
        )
        if secret:
            token = (
                auth_raw[7:].strip()
                if auth_raw.lower().startswith("bearer ")
                else auth_raw
            )
            aud = (env.get("GATEWAY_JWT_AUDIENCE") or "api-gateway").strip()
            iss = (env.get("GATEWAY_JWT_ISSUER") or "bitget-btc-ai-gateway").strip()
            try:
                import jwt as pyjwt
            except ImportError:
                add_check(
                    "JWT_HS256",
                    True,
                    "PyJWT nicht installiert — Signatur nicht geprueft (pip install -r requirements-dev.txt).",
                )
            else:
                try:
                    pyjwt.decode(
                        token,
                        secret,
                        algorithms=["HS256"],
                        audience=aud,
                        issuer=iss,
                    )
                    add_check(
                        "JWT_HS256", True, "Signatur, Ablauf und aud/iss plausibel."
                    )
                except pyjwt.ExpiredSignatureError:
                    add_check(
                        "JWT_HS256",
                        False,
                        "Abgelaufen — neu minten (scripts/mint_dashboard_gateway_jwt.py --update-env-file).",
                    )
                except pyjwt.InvalidSignatureError:
                    add_check(
                        "JWT_HS256",
                        False,
                        "Signatur ungueltig — GATEWAY_JWT_SECRET muss mit Gateway uebereinstimmen.",
                    )
                except Exception as exc:  # noqa: BLE001
                    add_check("JWT_HS256", False, f"Decode-Fehler: {str(exc)[:140]}")

    # HTTP: Gateway vom **diesem Rechner** aus (wie Next auf dem Host)
    if gw_url:
        h_url = f"{gw_url}/health"
        r_url = f"{gw_url}/ready"
        st_h, body_h = _http_get(h_url, timeout_sec=args.timeout)
        if st_h is None:
            add_check("GET_/health", False, f"Nicht erreichbar: {body_h[:200]}")
        elif 200 <= st_h < 300:
            add_check("GET_/health", True, f"HTTP {st_h}")
        else:
            add_check("GET_/health", False, f"HTTP {st_h} — {body_h[:120]}")

        st_r, body_r = _http_get(r_url, timeout_sec=args.timeout)
        ready_ok: bool | None = None
        ready_summary = ""
        if st_r is None:
            add_check("GET_/ready", False, f"Nicht erreichbar: {body_r[:200]}")
        elif st_r == 200:
            try:
                j = json.loads(body_r)
                ready_ok = bool(j.get("ready")) if isinstance(j, dict) else None
                chk = j.get("checks") if isinstance(j, dict) else None
                if isinstance(chk, dict):
                    parts = []
                    for k, v in list(chk.items())[:5]:
                        if isinstance(v, list) and len(v) >= 2:
                            parts.append(f"{k}={'ok' if v[0] is True else 'fail'}")
                    ready_summary = "; ".join(parts)
            except json.JSONDecodeError:
                ready_ok = None
            if ready_ok is True:
                add_check("GET_/ready", True, "ready=true")
            elif ready_ok is False:
                add_check(
                    "GET_/ready",
                    False,
                    f"ready=false — Upstreams im Gateway pruefen. Kurz: {ready_summary or body_r[:100]}",
                )
            else:
                add_check(
                    "GET_/ready",
                    True,
                    f"HTTP 200 (Body kein JSON ready-Flag): {body_r[:80]}",
                )
        else:
            add_check("GET_/ready", False, f"HTTP {st_r}")

    if llm_url:
        add_check(
            "LLM_ORCH_BASE_URL_or_HEALTH",
            True,
            f"Gesetzt ({llm_url[:60]}…) — vom Host ggf. nicht erreichbar wenn nur Docker-Hostname.",
        )

    # Empfehlungstext
    hints: list[str] = []
    if not auth_raw or "SET_ME" in auth_raw.upper():
        hints.append(
            "JWT schreiben: python scripts/mint_dashboard_gateway_jwt.py "
            f"--env-file {env_path.name} --update-env-file"
        )
        hints.append(
            "Danach: Next auf dem Host neu starten ODER Dashboard-Container: "
            "docker compose --env-file .env.local -f docker-compose.yml up -d --force-recreate dashboard"
        )
    if (
        gw_url
        and urlparse(gw_url).hostname
        and _docker_internal_host(str(urlparse(gw_url).hostname))
    ):
        hints.append(
            "API_GATEWAY_URL auf http://127.0.0.1:8000 pruefen, wenn Next ausserhalb Docker laeuft."
        )
    any_health_fail = any(
        c["name"] == "GET_/health" and not c["ok"]
        for c in report["checks"]
        if isinstance(c, dict)
    )
    if any_health_fail:
        hints.append(
            "Stack starten: pnpm dev:up  (oder bootstrap:local). Docker Desktop muss laufen."
        )

    report["hints"] = hints
    report["ok"] = not critical

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if not critical else 1

    print("=== local_stack_doctor ===")
    print(f"ENV: {env_path}")
    for c in report["checks"]:
        mark = (
            "OK " if c.get("ok") is True else "ERR" if c.get("ok") is False else "INFO"
        )
        print(f"  [{mark}] {c['name']}: {c['detail']}")
    if hints:
        print("")
        print("Naechste Schritte:")
        for h in hints:
            print(f"  - {h}")
    print("")
    if critical:
        print("Ergebnis: Es gibt blockierende Punkte (siehe ERR).")
        return 1
    print("Ergebnis: Keine blockierenden ENV-Punkte; Gateway vom Host aus erreichbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
