#!/usr/bin/env python3
"""
Reproduzierbare Verifikation der KI-Strecke „Operator Explain“.

Modi:
  orchestrator (Standard): POST direkt an llm-orchestrator
    /llm/analyst/operator_explain mit Header X-Internal-Service-Key (falls in ENV gesetzt).

  gateway: POST an API-Gateway /v1/llm/operator/explain mit Authorization
    aus DASHBOARD_GATEWAY_AUTHORIZATION (Bearer-JWT, gateway:read).

Voraussetzung: llm-orchestrator laeuft und ist erreichbar. Fuer deterministische Antworten ohne OpenAI:
  LLM_USE_FAKE_PROVIDER=true am Orchestrator.

Exit 0 wenn HTTP 200 und result.explanation_de nicht leer; sonst 1.
Keine Secrets in stdout (Key nur als gesetzt/nicht gesetzt).
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


def orch_base_url(env: dict[str, str]) -> str:
    b = (env.get("LLM_ORCH_BASE_URL") or os.environ.get("LLM_ORCH_BASE_URL") or "").strip().rstrip("/")
    if b:
        return b
    h = (env.get("HEALTH_URL_LLM_ORCHESTRATOR") or os.environ.get("HEALTH_URL_LLM_ORCHESTRATOR") or "").strip()
    if h:
        u = h.rstrip("/")
        lu = u.lower()
        if lu.endswith("/health"):
            return u[: -len("/health")]
        if lu.endswith("/ready"):
            return u[: -len("/ready")]
        return u
    return "http://127.0.0.1:8070"


def http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, object | str]:
    h = {**(headers or {})}
    req = urllib.request.Request(url, method="GET", headers=h)
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
            return e.code, json.loads(raw) if raw.strip() else {"raw": raw[:800]}
        except json.JSONDecodeError:
            return e.code, raw[:1200]


def http_post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 130.0,
) -> tuple[int, object | str]:
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, method="POST", headers=h)
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
            return e.code, json.loads(raw) if raw.strip() else {"raw": raw[:800]}
        except json.JSONDecodeError:
            return e.code, raw[:1200]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", type=Path, default=Path(".env.local"))
    p.add_argument(
        "--mode",
        choices=("orchestrator", "gateway"),
        default="orchestrator",
        help="Direkt Orchestrator oder vollstaendiger Gateway-Pfad (JWT)",
    )
    p.add_argument(
        "--probe-health",
        action="store_true",
        help="Vor dem POST GET /health am Orchestrator (OpenAI-Transport, Modell-ENV).",
    )
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    env_path = args.env_file if args.env_file.is_absolute() else root / args.env_file
    file_env = load_dotenv(env_path)

    def ge(key: str) -> str:
        return (os.environ.get(key) or file_env.get(key) or "").strip()

    body: dict[str, object] = {
        "question_de": "Was bedeutet Live-Gate in diesem Stack?",
        "readonly_context_json": {"verify_script": "verify_ai_operator_explain.py"},
    }

    print("=== verify_ai_operator_explain ===")
    print(f"mode={args.mode}")
    print(f"env_file={env_path} exists={env_path.is_file()}")

    if args.mode == "orchestrator":
        base = orch_base_url({**file_env, **{k: v for k, v in os.environ.items()}})
        ikey = ge("INTERNAL_API_KEY")
        hdrs: dict[str, str] = {}
        if ikey:
            hdrs["X-Internal-Service-Key"] = ikey
        if args.probe_health:
            hurl = f"{base}/health"
            print(f"GET {hurl} (--probe-health)")
            hc, hb = http_get_json(hurl, headers=hdrs, timeout=15.0)
            print(f"health HTTP {hc}")
            if isinstance(hb, dict):
                oa = hb.get("openai")
                if isinstance(oa, dict):
                    print(
                        "openai:",
                        json.dumps(oa, ensure_ascii=False, indent=2)[:1600],
                    )
                else:
                    print(json.dumps(hb, ensure_ascii=False, indent=2)[:1600])
        url = f"{base}/llm/analyst/operator_explain"
        print(f"POST {url}")
        print(f"X-Internal-Service-Key={'yes' if ikey else 'no (dev may allow anonymous)'}")
        try:
            code, payload = http_post_json(url, body, headers=hdrs, timeout=130.0)
        except urllib.error.URLError as exc:
            print(f"FAIL transport: {exc.reason!s}", file=sys.stderr)
            return 1
    else:
        bind = (ge("COMPOSE_EDGE_BIND") or "127.0.0.1").strip().strip('"').strip("'")
        if bind in ("0.0.0.0", "[::]", "::"):
            bind = "127.0.0.1"
        gw = (ge("API_GATEWAY_URL") or f"http://{bind}:8000").rstrip("/")
        auth = ge("DASHBOARD_GATEWAY_AUTHORIZATION")
        if not auth:
            print("FEHLT: DASHBOARD_GATEWAY_AUTHORIZATION fuer --mode gateway", file=sys.stderr)
            print("Mint: python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file", file=sys.stderr)
            return 1
        url = f"{gw}/v1/llm/operator/explain"
        hdrs = {"Authorization": auth}
        print(f"POST {url}")
        print("Authorization=Bearer ***")
        try:
            code, payload = http_post_json(url, body, headers=hdrs, timeout=130.0)
        except urllib.error.URLError as exc:
            print(f"FAIL transport: {exc.reason!s}", file=sys.stderr)
            return 1

    if code != 200:
        print(f"FAIL HTTP {code}", file=sys.stderr)
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000], file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print("FAIL body not object", file=sys.stderr)
        return 1

    result = payload.get("result")
    if not isinstance(result, dict):
        print("FAIL missing result object", file=sys.stderr)
        return 1

    expl = result.get("explanation_de")
    if not isinstance(expl, str) or not expl.strip():
        print("FAIL empty explanation_de", file=sys.stderr)
        return 1

    prov = payload.get("provider")
    mod = payload.get("model")
    print(
        f"OK provider={prov} model={mod} "
        f"task_type={payload.get('provenance', {}).get('task_type') if isinstance(payload.get('provenance'), dict) else 'n/a'}"
    )
    print("explanation_de (first 240 chars):")
    print(expl[:240] + ("…" if len(expl) > 240 else ""))
    if prov == "fake" and "[TEST-PROVIDER" not in expl:
        print("WARN: fake provider but explanation lacks [TEST-PROVIDER] marker", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
