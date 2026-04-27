#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (ROOT, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

import httpx

from scripts.bitget_readiness_check import load_dotenv

SECRET_KEYS = (
    "BITGET_API_KEY",
    "BITGET_API_SECRET",
    "BITGET_API_PASSPHRASE",
    "BITGET_DEMO_API_KEY",
    "BITGET_DEMO_API_SECRET",
    "BITGET_DEMO_API_PASSPHRASE",
)

SAFE_DEMO_MODES = {"dry-run", "readonly", "private-readonly", "demo-order-dry-run", "demo-order-smoke"}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _present(value: str | None) -> bool:
    raw = (value or "").strip()
    return bool(raw) and "change_me" not in raw.lower() and "<set_me" not in raw.lower()


def _redact_env(env: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in env.items():
        if k in SECRET_KEYS:
            out[k] = "set_redacted" if _present(str(v)) else "missing"
        else:
            out[k] = v
    return out


def _safe_float(value: str | None, default: float) -> float:
    try:
        return float(str(value or "").strip() or default)
    except Exception:
        return default


def _demo_headers(env: dict[str, str], *, method: str, path: str, query: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> dict[str, str]:
    query_string = f"?{urlencode(query)}" if query else ""
    body_text = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False) if body else ""
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}{query_string}{body_text}"
    secret = str(env.get("BITGET_DEMO_API_SECRET") or "")
    sign = base64.b64encode(hmac.new(secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()).decode("ascii")
    return {
        "ACCESS-KEY": str(env.get("BITGET_DEMO_API_KEY") or ""),
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": str(env.get("BITGET_DEMO_API_PASSPHRASE") or ""),
        "Content-Type": "application/json",
        "locale": str(env.get("BITGET_REST_LOCALE") or "en-US"),
        "paptrading": str(env.get("BITGET_DEMO_PAPTRADING_HEADER") or "1"),
    }


def _private_get(client: httpx.Client, env: dict[str, str], path: str, query: dict[str, str]) -> tuple[int, dict[str, Any]]:
    base = str(env.get("BITGET_DEMO_REST_BASE_URL") or "").rstrip("/")
    headers = _demo_headers(env, method="GET", path=path, query=query)
    r = client.get(f"{base}{path}", params=query, headers=headers)
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}
    return r.status_code, data if isinstance(data, dict) else {}


def _private_post(client: httpx.Client, env: dict[str, str], path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    base = str(env.get("BITGET_DEMO_REST_BASE_URL") or "").rstrip("/")
    headers = _demo_headers(env, method="POST", path=path, body=body)
    r = client.post(f"{base}{path}", content=json.dumps(body, separators=(",", ":"), ensure_ascii=False), headers=headers)
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}
    return r.status_code, data if isinstance(data, dict) else {}


@dataclass
class DemoReadiness:
    result: str
    blockers: list[str]
    warnings: list[str]
    checks: dict[str, Any]
    env_snapshot: dict[str, Any]


def build_demo_order_body(env: dict[str, str]) -> dict[str, Any]:
    symbol = str(env.get("BITGET_SYMBOL") or "BTCUSDT").strip().upper()
    product_type = str(env.get("DEMO_DEFAULT_PRODUCT_TYPE") or "USDT-FUTURES").strip()
    margin_coin = str(env.get("DEMO_DEFAULT_MARGIN_COIN") or "USDT").strip()
    margin_mode = str(env.get("DEMO_DEFAULT_MARGIN_MODE") or "isolated").strip().lower()
    size = str(env.get("DEMO_DEFAULT_ORDER_SIZE") or "0.001").strip()
    side = str(env.get("DEMO_DEFAULT_ORDER_SIDE") or "buy").strip().lower()
    order_type = str(env.get("DEMO_DEFAULT_ORDER_TYPE") or "market").strip().lower()
    force = str(env.get("DEMO_DEFAULT_FORCE") or "gtc").strip().lower()
    position_mode = str(env.get("DEMO_POSITION_MODE") or "one_way").strip().lower()
    trade_side = str(env.get("DEMO_TRADE_SIDE") or "").strip().lower()
    pos_side = str(env.get("DEMO_POSITION_SIDE") or "").strip().lower()
    price = str(env.get("DEMO_DEFAULT_PRICE") or "").strip()

    body: dict[str, Any] = {
        "symbol": symbol,
        "productType": product_type,
        "marginMode": margin_mode,
        "marginCoin": margin_coin,
        "size": size,
        "side": side,
        "orderType": order_type,
        "clientOid": f"bgai-demo-{int(time.time())}",
    }
    if order_type == "limit":
        body["force"] = force
        if price:
            body["price"] = price

    if position_mode == "hedge":
        body["tradeSide"] = trade_side or "open"
        if pos_side:
            body["posSide"] = pos_side
    else:
        body["reduceOnly"] = "NO"

    return body


def _demo_order_hint(code: str, msg: str) -> str:
    if code == "40774":
        return (
            "Bitget 40774: Position-Mode und Order-Payload passen nicht zusammen. "
            "Pruefe DEMO_POSITION_MODE. one_way: kein tradeSide/posSide; hedge: tradeSide=open/close."
        )
    if code and code not in ("00000", "0"):
        return f"Bitget Fehlercode {code}: {msg or 'ohne Meldung'}"
    return ""


def build_report(
    env: dict[str, str],
    mode: str,
    *,
    allow_demo_money: bool = False,
    output_json_path: Path | None = None,
) -> DemoReadiness:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {"mode": mode}

    if mode not in SAFE_DEMO_MODES:
        blockers.append(f"Unbekannter Demo-Modus: {mode}")

    exec_mode = str(env.get("EXECUTION_MODE") or "").strip().lower()
    live_trade_enable = _truthy(env.get("LIVE_TRADE_ENABLE"))
    demo_submit_enable = _truthy(env.get("DEMO_ORDER_SUBMIT_ENABLE"))
    demo_enabled = _truthy(env.get("BITGET_DEMO_ENABLED"))
    paptrading = str(env.get("BITGET_DEMO_PAPTRADING_HEADER") or "").strip()
    demo_key_ok = all(
        _present(env.get(k))
        for k in ("BITGET_DEMO_API_KEY", "BITGET_DEMO_API_SECRET", "BITGET_DEMO_API_PASSPHRASE")
    )
    live_keys_present = any(_present(env.get(k)) for k in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"))
    demo_base = str(env.get("BITGET_DEMO_REST_BASE_URL") or "").strip().lower()
    live_base = str(env.get("BITGET_API_BASE_URL") or "").strip().lower()

    checks["execution_mode"] = exec_mode or "missing"
    checks["live_trade_enable"] = str(live_trade_enable).lower()
    checks["demo_order_submit_enable"] = str(demo_submit_enable).lower()
    checks["bitget_demo_enabled"] = str(demo_enabled).lower()
    checks["demo_keys"] = "ok" if demo_key_ok else "missing"
    checks["live_keys_present"] = str(live_keys_present).lower()
    checks["paptrading_header"] = paptrading or "missing"
    checks["demo_endpoint"] = "ok" if demo_base.startswith("https://") else "missing_or_invalid"

    if exec_mode != "bitget_demo":
        blockers.append("EXECUTION_MODE muss bitget_demo sein.")
    if live_trade_enable:
        blockers.append("LIVE_TRADE_ENABLE muss false sein.")
    if not demo_enabled:
        blockers.append("BITGET_DEMO_ENABLED muss true sein.")
    if paptrading != "1":
        blockers.append("BITGET_DEMO_PAPTRADING_HEADER muss 1 sein.")
    if not demo_key_ok:
        blockers.append("Demo-Credentials fehlen (BITGET_DEMO_*).")
    if live_keys_present and not _truthy(env.get("BITGET_RELAX_CREDENTIAL_ISOLATION")):
        blockers.append("Live-Credentials muessen im Demo-Profil leer bleiben oder explizit isoliert sein.")
    if not demo_base.startswith("https://"):
        blockers.append("BITGET_DEMO_REST_BASE_URL ist unklar.")
    if live_base and demo_base and live_base == demo_base:
        warnings.append("Demo- und Live-REST-Basis sind identisch; paptrading Header strikt pruefen.")

    base_blockers = list(blockers)

    if mode in ("readonly", "private-readonly", "demo-order-dry-run", "demo-order-smoke") and not base_blockers:
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{demo_base.rstrip('/')}/api/v2/public/time")
                checks["server_time_http"] = str(r.status_code)
                if r.status_code >= 400:
                    blockers.append("Demo/Public-Serverzeit nicht erreichbar.")
        except Exception as exc:
            checks["server_time_http"] = "error"
            blockers.append(f"Demo/Public-Serverzeit nicht erreichbar: {type(exc).__name__}")
    else:
        checks["server_time_http"] = "skipped"

    product_type = str(env.get("DEMO_DEFAULT_PRODUCT_TYPE") or env.get("BITGET_PRODUCT_TYPE") or "USDT-FUTURES").strip()
    margin_coin = str(env.get("DEMO_DEFAULT_MARGIN_COIN") or env.get("BITGET_FUTURES_DEFAULT_MARGIN_COIN") or "USDT").strip()
    symbol = str(env.get("BITGET_SYMBOL") or "BTCUSDT").strip().upper()

    if mode == "private-readonly" and not blockers:
        with httpx.Client(timeout=10.0) as client:
            status, payload = _private_get(
                client,
                env,
                "/api/v2/mix/account/accounts",
                {"productType": product_type},
            )
        checks["private_accounts_http"] = str(status)
        checks["private_accounts_code"] = str(payload.get("code") or "missing")
        if status >= 400 or str(payload.get("code") or "") not in ("00000", "0"):
            blockers.append("Demo private-readonly Account-Endpunkt nicht erfolgreich.")

    if mode == "demo-order-dry-run":
        body = build_demo_order_body(env)
        position_mode = str(env.get("DEMO_POSITION_MODE") or "one_way").strip().lower()
        size = str(body.get("size") or "0.001")
        notional_cap = _safe_float(env.get("DEMO_MAX_ORDER_NOTIONAL_USDT"), 25.0)
        checks["demo_position_mode"] = position_mode
        checks["demo_order_payload"] = body
        checks["demo_order_fields"] = ",".join(sorted(body.keys()))
        checks["demo_order_has_tradeside"] = str("tradeSide" in body).lower()
        checks["demo_order_has_reduceonly"] = str("reduceOnly" in body).lower()
        checks["demo_order_payload_summary"] = (
            f"symbol={symbol}, productType={product_type}, marginCoin={margin_coin}, size={size}, maxNotional={notional_cap}"
        )
        checks["demo_order_executed"] = "false"

    if mode == "demo-order-smoke":
        if not allow_demo_money:
            blockers.append("Demo-Order-Smoke braucht Flag --i-understand-this-uses-demo-money.")
        if not demo_submit_enable:
            blockers.append("DEMO_ORDER_SUBMIT_ENABLE muss true sein fuer echte Demo-Order.")
        allowed_symbols = [s.strip().upper() for s in str(env.get("DEMO_ALLOWED_SYMBOLS") or "").split(",") if s.strip()]
        if symbol not in allowed_symbols:
            blockers.append("BITGET_SYMBOL ist nicht in DEMO_ALLOWED_SYMBOLS.")
        position_mode = str(env.get("DEMO_POSITION_MODE") or "one_way").strip().lower()
        body = build_demo_order_body(env)
        checks["demo_position_mode"] = position_mode
        checks["demo_order_payload"] = body
        checks["demo_order_fields"] = ",".join(sorted(body.keys()))
        checks["demo_order_has_tradeside"] = str("tradeSide" in body).lower()
        checks["demo_order_has_reduceonly"] = str("reduceOnly" in body).lower()
        checks["demo_order_executed"] = "false"
        if not blockers:
            with httpx.Client(timeout=10.0) as client:
                status, payload = _private_post(client, env, "/api/v2/mix/order/place-order", body)
            checks["demo_order_http"] = str(status)
            order_code = str(payload.get("code") or "missing")
            order_msg = str(payload.get("msg") or "")
            order_hint = _demo_order_hint(order_code, order_msg)
            checks["demo_order_code"] = order_code
            checks["demo_order_msg"] = order_msg
            checks["demo_order_hint"] = order_hint
            if status >= 400 or order_code not in ("00000", "0"):
                blockers.append(order_hint or "Echte Demo-Order wurde nicht erfolgreich angenommen.")
            else:
                checks["demo_order_executed"] = "true"

    if blockers:
        result = "FAIL"
    elif warnings:
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    report = DemoReadiness(
        result=result,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
        env_snapshot=_redact_env(
            {
                "EXECUTION_MODE": env.get("EXECUTION_MODE", ""),
                "LIVE_TRADE_ENABLE": env.get("LIVE_TRADE_ENABLE", ""),
                "DEMO_ORDER_SUBMIT_ENABLE": env.get("DEMO_ORDER_SUBMIT_ENABLE", ""),
                "BITGET_DEMO_ENABLED": env.get("BITGET_DEMO_ENABLED", ""),
                "BITGET_API_BASE_URL": env.get("BITGET_API_BASE_URL", ""),
                "BITGET_DEMO_REST_BASE_URL": env.get("BITGET_DEMO_REST_BASE_URL", ""),
                "BITGET_DEMO_PAPTRADING_HEADER": env.get("BITGET_DEMO_PAPTRADING_HEADER", ""),
                **{k: env.get(k, "") for k in SECRET_KEYS},
            }
        ),
    )
    if output_json_path:
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


def to_markdown(rep: DemoReadiness) -> str:
    lines = [
        "# Bitget Demo Readiness",
        "",
        f"- Ergebnis: `{rep.result}`",
        f"- Modus: `{rep.checks.get('mode', 'unknown')}`",
        f"- Demo-Order ausgeführt: `{rep.checks.get('demo_order_executed', 'false')}`",
        "- Live-Trading-Freigabe: `NEIN`",
        "",
        "## Checks",
        *[f"- `{k}`: `{v}`" for k, v in rep.checks.items()],
        "",
        "## Blocker",
        *([f"- {b}" for b in rep.blockers] if rep.blockers else ["- keine"]),
        "",
        "## Warnungen",
        *([f"- {w}" for w in rep.warnings] if rep.warnings else ["- keine"]),
        "",
        "## Env Snapshot (redacted)",
        "```json",
        json.dumps(rep.env_snapshot, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--mode", choices=("readonly", "private-readonly", "demo-order-dry-run", "demo-order-smoke"), default="readonly")
    p.add_argument("--i-understand-this-uses-demo-money", action="store_true")
    p.add_argument("--output-md", type=Path)
    p.add_argument("--output-json", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}")
        return 1
    env = load_dotenv(args.env_file)
    mode = "dry-run" if args.dry_run else args.mode
    report = build_report(
        env,
        mode,
        allow_demo_money=bool(args.i_understand_this_uses_demo_money),
        output_json_path=args.output_json,
    )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(to_markdown(report), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"bitget_demo_readiness: result={report.result} mode={mode}")
        for b in report.blockers:
            print(f"BLOCKER {b}")
        for w in report.warnings:
            print(f"WARNING {w}")
    return 1 if report.result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
