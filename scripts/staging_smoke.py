#!/usr/bin/env python3
"""
Staging-/Pre-Prod-Smoke: ein kritischer Gateway-Pfad plus KI-Pfad (Operator Explain).

Schritte:
  1) GET  {API_GATEWAY_URL}/health
  2) GET  {API_GATEWAY_URL}/ready
  3) GET  {API_GATEWAY_URL}/v1/system/health  (Authorization: DASHBOARD_GATEWAY_AUTHORIZATION)
  4) POST {API_GATEWAY_URL}/v1/llm/operator/explain (gleicher Authorization)

Exit 0 nur wenn alle erwarteten HTTP-Codes und Mindest-JSON-Struktur stimmen.
Keine stillen URL-Fallbacks: API_GATEWAY_URL und DASHBOARD_GATEWAY_AUTHORIZATION muessen in der
ENV-Datei gesetzt sein (keine Platzhalter).

Optional --disallow-loopback-gateway: schlaegt fehl, wenn die Gateway-Host-URL localhost/127.0.0.1 ist
(nuetzlich, um echte Staging-Hosts zu erzwingen).
"""

from __future__ import annotations

import argparse
import json
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


def _bad(val: str) -> bool:
    t = val.strip()
    if not t:
        return True
    u = t.upper()
    return "<SET_ME>" in u or u == "SET_ME" or u == "CHANGE_ME"


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 30.0,
) -> tuple[int, object | str]:
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return code, {}
            return code, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return e.code, raw[:800]


def _host_is_loopback(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        h = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return h in ("localhost", "127.0.0.1", "::1")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, required=True, help="z. B. .env.shadow")
    p.add_argument(
        "--disallow-loopback-gateway",
        action="store_true",
        help="Fehlschlag wenn API_GATEWAY_URL auf localhost/127.0.0.1 zeigt",
    )
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    env_path = args.env_file if args.env_file.is_absolute() else root / args.env_file
    if not env_path.is_file():
        print(f"FEHLT: {env_path}", file=sys.stderr)
        return 1

    env = load_dotenv(env_path)
    gw = (env.get("API_GATEWAY_URL") or "").strip().rstrip("/")
    auth = (env.get("DASHBOARD_GATEWAY_AUTHORIZATION") or "").strip()

    if _bad(gw):
        print("staging_smoke: API_GATEWAY_URL fehlt oder Platzhalter — in Staging explizit setzen.", file=sys.stderr)
        return 1
    if _bad(auth):
        print(
            "staging_smoke: DASHBOARD_GATEWAY_AUTHORIZATION fehlt oder Platzhalter — JWT fuer gateway:read setzen.",
            file=sys.stderr,
        )
        return 1

    if args.disallow_loopback_gateway and _host_is_loopback(gw):
        print(
            f"staging_smoke: API_GATEWAY_URL={gw!r} ist Loopback — fuer echtes Staging oeffentlichen/LB-Host verwenden.",
            file=sys.stderr,
        )
        return 1

    print("=== staging_smoke ===")
    print(f"env_file={env_path}")
    print(f"API_GATEWAY_URL={gw}")
    print("Authorization=Bearer ***")

    failed = False

    code, body = http_json("GET", f"{gw}/health", timeout=12.0)
    ok = code == 200
    print(f"[1] GET /health -> HTTP {code} ok={ok}")
    if not ok:
        failed = True

    code2, body2 = http_json("GET", f"{gw}/ready", timeout=20.0)
    ready_ok = isinstance(body2, dict) and body2.get("ready") is True
    print(f"[2] GET /ready -> HTTP {code2} ready={ready_ok}")
    if code2 != 200 or not ready_ok:
        failed = True
        if isinstance(body2, dict) and body2.get("checks"):
            print(f"    checks={json.dumps(body2.get('checks'), ensure_ascii=False)[:600]}")

    h3, b3 = http_json(
        "GET",
        f"{gw}/v1/system/health",
        headers={"Authorization": auth},
        timeout=20.0,
    )
    sys_ok = (
        h3 == 200
        and isinstance(b3, dict)
        and b3.get("database") == "ok"
        and b3.get("redis") == "ok"
    )
    print(
        f"[3] GET /v1/system/health -> HTTP {h3} database={b3.get('database') if isinstance(b3, dict) else '?'} "
        f"redis={b3.get('redis') if isinstance(b3, dict) else '?'}"
    )
    if not sys_ok:
        failed = True

    explain_body = json.dumps(
        {
            "question_de": "Staging-Smoke: Was ist das Live-Gate?",
            "readonly_context_json": {"source": "scripts/staging_smoke.py"},
        }
    ).encode("utf-8")
    h4, b4 = http_json(
        "POST",
        f"{gw}/v1/llm/operator/explain",
        headers={"Authorization": auth, "Content-Type": "application/json"},
        data=explain_body,
        timeout=130.0,
    )
    llm_ok = False
    if h4 == 200 and isinstance(b4, dict):
        res = b4.get("result")
        expl = isinstance(res, dict) and res.get("explanation_de")
        llm_ok = isinstance(expl, str) and bool(expl.strip())
    print(f"[4] POST /v1/llm/operator/explain -> HTTP {h4} explanation_ok={llm_ok}")
    if not llm_ok:
        failed = True
        snippet = json.dumps(b4, ensure_ascii=False) if not isinstance(b4, str) else b4
        print(f"    body_snip={str(snippet)[:500]}", file=sys.stderr)

    if failed:
        print("\nERGEBNIS: staging_smoke fehlgeschlagen — Logs/Gateway-ENV pruefen.", file=sys.stderr)
        print("Doku: STAGING_PARITY.md | KI-Details: AI_FLOW.md", file=sys.stderr)
        return 1
    print("\nERGEBNIS: staging_smoke OK (Health + System-Health + Operator-Explain).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
