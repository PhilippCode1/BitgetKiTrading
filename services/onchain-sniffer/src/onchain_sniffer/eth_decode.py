from __future__ import annotations

import logging
from typing import Any

from eth_abi import decode as abi_decode

from onchain_sniffer.dex_routers import (
    SELECTOR_EXACT_INPUT_SINGLE,
    SELECTOR_SWAP_EXACT_ETH_FOR_TOKENS,
    SELECTOR_SWAP_EXACT_TOKENS_FOR_ETH,
    SELECTOR_SWAP_EXACT_TOKENS_FOR_TOKENS,
    WETH_MAINNET,
)

logger = logging.getLogger("onchain_sniffer.eth_decode")


def _norm_hex(data: str | bytes) -> str:
    if isinstance(data, bytes):
        return "0x" + data.hex()
    s = str(data or "").strip().lower()
    if not s.startswith("0x"):
        s = "0x" + s
    return s


def selector_of(data: str | bytes) -> str:
    hx = _norm_hex(data)
    if len(hx) < 10:
        return ""
    return hx[:10]


def _short_addr(a: str) -> str:
    x = a.lower().replace("0x", "")
    if len(x) < 10:
        return a
    return "0x" + x[:6] + "…" + x[-4:]


def tx_value_wei(tx: dict[str, Any]) -> int:
    v = tx.get("value")
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s.startswith("0x"):
        return int(s, 16)
    return int(s)


def decode_swap_context(tx: dict[str, Any], eth_usd: float) -> dict[str, Any] | None:
    """
    Schaetzt Notional (USD), DEX-Label, Token-Paar-Kurzform und Richtung.
    Rueckgabe None wenn nicht dekodierbar.
    """
    inp = _norm_hex(tx.get("input") or "0x")
    sel = selector_of(inp)
    value_wei = tx_value_wei(tx)
    body = bytes.fromhex(inp[2:][8:]) if len(inp) > 10 else b""

    weth_l = WETH_MAINNET

    try:
        if sel == SELECTOR_SWAP_EXACT_ETH_FOR_TOKENS and value_wei > 0:
            amount_out_min, path, _to, _deadline = abi_decode(
                ["uint256", "address[]", "address", "uint256"],
                body,
            )
            notional_eth = value_wei / 1e18
            pair = _pair_label(path)
            return {
                "dex": "uniswap_v2",
                "token_pair": pair,
                "estimated_volume_usd": notional_eth * eth_usd,
                "direction": _direction_from_path(path),
                "amount_out_min": int(amount_out_min),
                "path": [p.lower() for p in path],
            }
        if sel == SELECTOR_SWAP_EXACT_TOKENS_FOR_ETH:
            amount_in, amount_out_min, path, _to, _deadline = abi_decode(
                ["uint256", "uint256", "address[]", "address", "uint256"],
                body,
            )
            if not path:
                return None
            notional_eth = float(amount_in) / 1e18 * _weth_weight(path, weth_l)
            return {
                "dex": "uniswap_v2",
                "token_pair": _pair_label(path),
                "estimated_volume_usd": notional_eth * eth_usd if notional_eth > 0 else float(amount_in) / 1e6,
                "direction": _direction_from_path(path),
                "amount_in": int(amount_in),
                "amount_out_min": int(amount_out_min),
                "path": [p.lower() for p in path],
            }
        if sel == SELECTOR_SWAP_EXACT_TOKENS_FOR_TOKENS:
            amount_in, amount_out_min, path, _to, _deadline = abi_decode(
                ["uint256", "uint256", "address[]", "address", "uint256"],
                body,
            )
            if not path:
                return None
            w = _weth_weight(path, weth_l)
            vol = float(amount_in) / 1e18 * w * eth_usd + float(amount_in) / 1e6 * (1.0 - min(1.0, w))
            return {
                "dex": "uniswap_v2",
                "token_pair": _pair_label(path),
                "estimated_volume_usd": vol,
                "direction": "unknown",
                "amount_in": int(amount_in),
                "amount_out_min": int(amount_out_min),
                "path": [p.lower() for p in path],
            }
        if sel == SELECTOR_EXACT_INPUT_SINGLE:
            params = abi_decode(
                [
                    "tuple(address,address,uint24,address,uint256,uint256,uint256,uint160)",
                ],
                body,
            )[0]
            token_in, token_out, _fee, _recipient, _deadline, amount_in, _amount_out_min, _sqrt_limit = params
            ti, tout = token_in.lower(), token_out.lower()
            if weth_l in (ti, tout):
                amt = int(amount_in)
                notional_eth = amt / 1e18
                pair = f"{_short_addr(token_in)}->{_short_addr(token_out)}"
                direction = "buy" if ti == weth_l else "sell"
                return {
                    "dex": "uniswap_v3",
                    "token_pair": pair,
                    "estimated_volume_usd": notional_eth * eth_usd,
                    "direction": direction,
                    "amount_in": amt,
                    "path": [ti, tout],
                }
    except Exception as exc:
        logger.debug("decode_swap_context failed sel=%s err=%s", sel, exc)
        return None

    if value_wei > 0 and len(inp) <= 10:
        notional_eth = value_wei / 1e18
        return {
            "dex": "unknown_eth_transfer",
            "token_pair": "ETH",
            "estimated_volume_usd": notional_eth * eth_usd,
            "direction": "unknown",
            "path": [],
        }

    return None


def _pair_label(path: list[str]) -> str:
    if len(path) >= 2:
        return f"{_short_addr(path[0])}/{_short_addr(path[-1])}"
    if len(path) == 1:
        return _short_addr(path[0])
    return "unknown"


def _direction_from_path(path: list[str]) -> str:
    if len(path) < 2:
        return "unknown"
    p0, p1 = path[0].lower(), path[1].lower()
    if p0 == WETH_MAINNET:
        return "buy"
    if p1 == WETH_MAINNET:
        return "sell"
    return "unknown"


def _weth_weight(path: list[str], weth: str) -> float:
    pl = [p.lower() for p in path]
    return 1.0 if any(p == weth for p in pl) else 0.0
