#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for p in (ROOT, SHARED_SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from scripts.bitget_demo_readiness import _present, _private_get, _private_post, _truthy
from scripts.bitget_readiness_check import load_dotenv

SAFE_MODES = {"readonly", "close-dry-run", "close-smoke"}


@dataclass
class DemoReconcileEvidence:
    result: str
    reconcile_status: str
    blockers: list[str]
    warnings: list[str]
    checks: dict[str, Any]
    live_trading_allowed: bool
    private_live_allowed: bool


def _safe_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("list", "items", "orderList", "entrustedList"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _extract_position(positions: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    wanted = symbol.upper()
    for pos in positions:
        if str(pos.get("symbol") or "").upper() == wanted:
            size_raw = str(pos.get("total") or pos.get("holdSize") or pos.get("available") or "0").strip()
            if size_raw and size_raw not in ("0", "0.0", "0.00", "0.000", "0.0000", "0.00000"):
                return pos
    return None


def _detect_position_side(pos: dict[str, Any]) -> str:
    hold_side = str(pos.get("holdSide") or pos.get("posSide") or "").strip().lower()
    if hold_side in ("long", "short"):
        return hold_side
    side = str(pos.get("side") or "").strip().lower()
    if side in ("long", "short"):
        return side
    return "unknown"


def _position_size(pos: dict[str, Any]) -> str:
    return str(pos.get("total") or pos.get("holdSize") or pos.get("available") or "0").strip() or "0"


def build_close_order_payload(env: dict[str, str], position: dict[str, Any]) -> dict[str, Any]:
    product_type = str(env.get("DEMO_DEFAULT_PRODUCT_TYPE") or env.get("BITGET_PRODUCT_TYPE") or "USDT-FUTURES").strip()
    margin_coin = str(
        position.get("marginCoin")
        or env.get("DEMO_DEFAULT_MARGIN_COIN")
        or env.get("BITGET_FUTURES_DEFAULT_MARGIN_COIN")
        or "USDT"
    ).strip()
    symbol = str(position.get("symbol") or env.get("DEMO_RECONCILE_SYMBOL") or env.get("BITGET_SYMBOL") or "BTCUSDT").strip().upper()
    side_detected = _detect_position_side(position)
    position_mode = str(env.get("DEMO_POSITION_MODE") or "hedge").strip().lower()
    if position_mode == "hedge":
        if side_detected == "long":
            close_side = "buy"
            close_rule = "hedge_long_close_buy"
        elif side_detected == "short":
            close_side = "sell"
            close_rule = "hedge_short_close_sell"
        else:
            close_side = ""
            close_rule = "unknown_side_blocked"
    else:
        if side_detected == "long":
            close_side = "sell"
            close_rule = "one_way_long_close_sell_reduce_only"
        elif side_detected == "short":
            close_side = "buy"
            close_rule = "one_way_short_close_buy_reduce_only"
        else:
            close_side = ""
            close_rule = "unknown_side_blocked"
    size = _position_size(position)
    max_size = str(env.get("DEMO_CLOSE_POSITION_MAX_SIZE") or "").strip()
    if max_size and max_size != "0":
        try:
            size = str(min(float(size), float(max_size)))
        except Exception:
            pass
    payload: dict[str, Any] = {
        "symbol": symbol,
        "productType": product_type,
        "marginMode": str(env.get("DEMO_DEFAULT_MARGIN_MODE") or "isolated").strip().lower(),
        "marginCoin": margin_coin,
        "size": size,
        "side": close_side,
        "orderType": "market",
        "clientOid": f"bgai-demo-close-{int(time.time())}",
    }
    if position_mode == "hedge":
        payload["tradeSide"] = "close"
    else:
        payload["reduceOnly"] = "YES"
    payload["closeOrderSideRule"] = close_rule
    return payload


def _base_checks(env: dict[str, str], mode: str) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {"mode": mode}
    exec_mode = str(env.get("EXECUTION_MODE") or "").strip().lower()
    live_trade_enable = _truthy(env.get("LIVE_TRADE_ENABLE"))
    demo_enabled = _truthy(env.get("BITGET_DEMO_ENABLED"))
    paptrading = str(env.get("BITGET_DEMO_PAPTRADING_HEADER") or "").strip()
    demo_key_ok = all(_present(env.get(k)) for k in ("BITGET_DEMO_API_KEY", "BITGET_DEMO_API_SECRET", "BITGET_DEMO_API_PASSPHRASE"))
    live_keys_present = any(_present(env.get(k)) for k in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"))
    checks["execution_mode"] = exec_mode or "missing"
    checks["live_trade_enable"] = str(live_trade_enable).lower()
    checks["bitget_demo_enabled"] = str(demo_enabled).lower()
    checks["paptrading_header"] = paptrading or "missing"
    checks["demo_keys"] = "ok" if demo_key_ok else "missing"
    checks["live_keys_present"] = str(live_keys_present).lower()
    checks["live_trading_allowed"] = "false"
    checks["private_live_allowed"] = "false"
    checks["close_order_executed"] = "false"
    checks["close_order_code"] = "not_run"
    checks["close_order_msg"] = ""
    checks["close_order_hint"] = ""
    checks["close_order_payload"] = {}
    checks["close_order_required"] = "false"
    checks["close_order_side_rule"] = "not_set"
    checks["close_order_payload_side"] = ""
    checks["close_order_payload_tradeSide"] = ""
    checks["reconcile_status"] = "NOT_ENOUGH_EVIDENCE"
    if mode not in SAFE_MODES:
        blockers.append(f"Unbekannter Modus: {mode}")
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
    if live_keys_present:
        blockers.append("Live-Credentials muessen im Demo-Reconcile-Profil leer sein.")
    return blockers, warnings, checks


def build_reconcile_report(
    env: dict[str, str],
    mode: str,
    *,
    allow_close_demo_position: bool = False,
) -> DemoReconcileEvidence:
    blockers, warnings, checks = _base_checks(env, mode)
    symbol = str(env.get("DEMO_RECONCILE_SYMBOL") or env.get("BITGET_SYMBOL") or "BTCUSDT").strip().upper()
    product_type = str(env.get("DEMO_DEFAULT_PRODUCT_TYPE") or env.get("BITGET_PRODUCT_TYPE") or "USDT-FUTURES").strip()
    checks["detected_symbol"] = symbol
    checks["detected_position_side"] = "none"
    checks["detected_size"] = "0"
    checks["detected_margin_coin"] = str(env.get("DEMO_DEFAULT_MARGIN_COIN") or "USDT").strip()
    checks["account_ok"] = "false"
    checks["positions_http"] = "not_run"
    checks["positions_code"] = "not_run"
    checks["positions_count"] = "0"
    checks["open_orders_http"] = "not_run"
    checks["open_orders_code"] = "not_run"
    checks["open_orders_count"] = "0"
    checks["order_history_http"] = "endpoint_missing"
    checks["order_history_code"] = "endpoint_missing"
    checks["order_history_count"] = "0"
    checks["close_mode_flag_required"] = str(mode == "close-smoke").lower()
    checks["demo_evidence_stage"] = "demo_reconcile_verified" if mode in ("readonly", "close-dry-run") else "implemented"

    base_url = str(env.get("BITGET_DEMO_REST_BASE_URL") or "").rstrip("/")
    if not base_url.startswith("https://"):
        blockers.append("BITGET_DEMO_REST_BASE_URL ist unklar.")

    if mode == "close-smoke" and not allow_close_demo_position:
        blockers.append("Close-Smoke braucht Flag --i-understand-this-closes-demo-position.")

    positions: list[dict[str, Any]] = []
    open_orders: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None

    if not blockers:
        try:
            with httpx.Client(timeout=10.0) as client:
                public_time = client.get(f"{base_url}/api/v2/public/time")
                checks["server_time_http"] = str(public_time.status_code)
                if public_time.status_code >= 400:
                    blockers.append("Demo/Public-Serverzeit nicht erreichbar.")
        except Exception as exc:
            checks["server_time_http"] = "error"
            blockers.append(f"Demo/Public-Serverzeit nicht erreichbar: {type(exc).__name__}")

    if not blockers:
        with httpx.Client(timeout=10.0) as client:
            account_http, account_payload = _private_get(client, env, "/api/v2/mix/account/accounts", {"productType": product_type})
            checks["account_ok"] = str(account_http < 400 and str(account_payload.get("code") or "") in ("00000", "0")).lower()
            checks["account_http"] = str(account_http)
            checks["account_code"] = str(account_payload.get("code") or "missing")

            pos_http, pos_payload = _private_get(client, env, "/api/v2/mix/position/all-position", {"productType": product_type})
            checks["positions_http"] = str(pos_http)
            checks["positions_code"] = str(pos_payload.get("code") or "missing")
            positions = _safe_list(pos_payload)
            checks["positions_count"] = str(len(positions))

            oo_http, oo_payload = _private_get(
                client,
                env,
                "/api/v2/mix/order/orders-pending",
                {"productType": product_type, "symbol": symbol},
            )
            checks["open_orders_http"] = str(oo_http)
            checks["open_orders_code"] = str(oo_payload.get("code") or "missing")
            open_orders = _safe_list(oo_payload)
            checks["open_orders_count"] = str(len(open_orders))

            hist_http, hist_payload = _private_get(
                client,
                env,
                "/api/v2/mix/order/orders-history",
                {"productType": product_type, "symbol": symbol, "limit": "20"},
            )
            checks["order_history_http"] = str(hist_http)
            checks["order_history_code"] = str(hist_payload.get("code") or "missing")
            checks["order_history_count"] = str(len(_safe_list(hist_payload)))

            position = _extract_position(positions, symbol)
            if position:
                checks["detected_symbol"] = str(position.get("symbol") or symbol).upper()
                checks["detected_position_side"] = _detect_position_side(position)
                checks["detected_size"] = _position_size(position)
                checks["detected_margin_coin"] = str(position.get("marginCoin") or checks["detected_margin_coin"]).strip()
                checks["close_order_required"] = "true"
                close_payload = build_close_order_payload(env, position)
                close_rule = str(close_payload.pop("closeOrderSideRule", "not_set"))
                checks["close_order_payload"] = close_payload
                checks["close_order_side_rule"] = close_rule
                checks["close_order_payload_side"] = str(close_payload.get("side") or "")
                checks["close_order_payload_tradeSide"] = str(close_payload.get("tradeSide") or "")
                if checks["detected_position_side"] not in ("long", "short"):
                    blockers.append("Position side unknown; close order blocked.")
                if str(close_payload.get("tradeSide") or "").lower() == "open":
                    blockers.append("Close-Payload darf niemals tradeSide=open sein.")
            else:
                checks["close_order_payload"] = {}
                checks["close_order_required"] = "false"

            if mode == "close-smoke" and not blockers and position:
                close_payload = checks["close_order_payload"] if isinstance(checks["close_order_payload"], dict) else {}
                position_mode = str(env.get("DEMO_POSITION_MODE") or "hedge").strip().lower()
                if position_mode == "hedge" and str(close_payload.get("tradeSide") or "").lower() != "close":
                    blockers.append("Close-Smoke darf in hedge nur tradeSide=close senden.")
                if position_mode != "hedge" and str(close_payload.get("tradeSide") or "").strip():
                    blockers.append("Close-Smoke darf in one_way kein tradeSide senden.")
                elif not _truthy(env.get("DEMO_CLOSE_POSITION_ENABLE")):
                    blockers.append("DEMO_CLOSE_POSITION_ENABLE muss true sein fuer close-smoke mit Position.")
                else:
                    close_http, close_result = _private_post(client, env, "/api/v2/mix/order/place-order", close_payload)
                    checks["close_order_http"] = str(close_http)
                    checks["close_order_code"] = str(close_result.get("code") or "missing")
                    checks["close_order_msg"] = str(close_result.get("msg") or "")
                    if checks["close_order_code"] == "22002":
                        checks["close_order_hint"] = (
                            "Bitget 22002: No position to close. In Hedge Mode bedeutet das oft, dass side/tradeSide "
                            "nicht zur offenen Positionsrichtung passt oder die Position bereits geschlossen ist."
                        )
                    if close_http < 400 and checks["close_order_code"] in ("00000", "0"):
                        checks["close_order_executed"] = "true"
                    else:
                        blockers.append(checks["close_order_hint"] or "Demo-Close-Order wurde nicht erfolgreich angenommen.")

    if blockers:
        reconcile_status = "FAILED"
        result = "FAILED"
    else:
        has_position = checks["close_order_required"] == "true"
        has_open_orders = checks["open_orders_count"] not in ("0", "not_run")
        if mode == "close-smoke":
            if not has_position:
                reconcile_status = "CLEAN"
                result = "CLEAN"
            elif checks["close_order_executed"] == "true":
                reconcile_status = "CLOSE_VERIFIED"
                result = "CLOSE_VERIFIED"
            else:
                reconcile_status = "CLOSE_READY"
                result = "NOT_ENOUGH_EVIDENCE"
        elif mode == "close-dry-run":
            if has_position:
                reconcile_status = "CLOSE_READY"
                result = "CLOSE_READY"
            elif has_open_orders:
                reconcile_status = "OPEN_ORDERS_DETECTED"
                result = "OPEN_ORDERS_DETECTED"
            else:
                reconcile_status = "CLEAN"
                result = "CLEAN"
        else:
            if has_position:
                reconcile_status = "OPEN_POSITION_DETECTED"
                result = "OPEN_POSITION_DETECTED"
            elif has_open_orders:
                reconcile_status = "OPEN_ORDERS_DETECTED"
                result = "OPEN_ORDERS_DETECTED"
            else:
                reconcile_status = "CLEAN"
                result = "CLEAN"
    checks["reconcile_status"] = reconcile_status
    if reconcile_status == "CLOSE_VERIFIED":
        checks["demo_evidence_stage"] = "demo_close_verified"
    elif reconcile_status in ("OPEN_POSITION_DETECTED", "OPEN_ORDERS_DETECTED", "CLOSE_READY", "CLEAN"):
        checks["demo_evidence_stage"] = "demo_reconcile_verified"

    return DemoReconcileEvidence(
        result=result,
        reconcile_status=reconcile_status,
        blockers=blockers,
        warnings=warnings,
        checks=checks,
        live_trading_allowed=False,
        private_live_allowed=False,
    )


def to_markdown(rep: DemoReconcileEvidence) -> str:
    lines = [
        "# Demo Reconcile Evidence Report",
        "",
        f"- Ergebnis: `{rep.result}`",
        f"- Reconcile-Status: `{rep.reconcile_status}`",
        f"- live_trading_allowed: `{str(rep.live_trading_allowed).lower()}`",
        f"- private_live_allowed: `{str(rep.private_live_allowed).lower()}`",
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
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env-file", type=Path, default=Path(".env.demo"))
    p.add_argument("--mode", choices=tuple(sorted(SAFE_MODES)), default="readonly")
    p.add_argument("--i-understand-this-closes-demo-position", action="store_true")
    p.add_argument("--output-md", type=Path, default=Path("reports/demo_reconcile_evidence.md"))
    p.add_argument("--output-json", type=Path, default=Path("reports/demo_reconcile_evidence.json"))
    p.add_argument("--archive-success", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if not args.env_file.is_file():
        print(f"ERROR env_file_missing: {args.env_file}")
        return 1
    env = load_dotenv(args.env_file)
    rep = build_reconcile_report(
        env,
        args.mode,
        allow_close_demo_position=bool(args.i_understand_this_closes_demo_position),
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    md_content = to_markdown(rep)
    json_content = json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True)
    args.output_md.write_text(md_content, encoding="utf-8")
    args.output_json.write_text(json_content, encoding="utf-8")
    if args.archive_success and rep.result in ("CLOSE_VERIFIED", "CLEAN"):
        stable_md = args.output_md.with_name(f"demo_reconcile_evidence_{rep.result}.md")
        stable_json = args.output_json.with_name(f"demo_reconcile_evidence_{rep.result}.json")
        stable_md.write_text(md_content, encoding="utf-8")
        stable_json.write_text(json_content, encoding="utf-8")
        ts = time.strftime("%Y%m%d_%H%M%S")
        ts_md = args.output_md.with_name(f"demo_reconcile_evidence_{rep.result}_{ts}.md")
        ts_json = args.output_json.with_name(f"demo_reconcile_evidence_{rep.result}_{ts}.json")
        ts_md.write_text(md_content, encoding="utf-8")
        ts_json.write_text(json_content, encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(rep), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"demo_reconcile_evidence: result={rep.result} reconcile_status={rep.reconcile_status}")
    return 1 if rep.result in ("FAILED", "NOT_ENOUGH_EVIDENCE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
