from __future__ import annotations

from eth_abi import encode as abi_encode

from onchain_sniffer.dex_routers import SELECTOR_SWAP_EXACT_ETH_FOR_TOKENS, WETH_MAINNET
from onchain_sniffer.eth_decode import decode_swap_context
from onchain_sniffer.config import OnchainSnifferSettings
from onchain_sniffer.impact_rs import estimate_slippage_bps, heuristic_slippage_bps_py


def test_decode_swap_exact_eth_for_tokens() -> None:
    usdc = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    path = [WETH_MAINNET, usdc]
    body = abi_encode(
        ["uint256", "address[]", "address", "uint256"],
        [0, path, "0x0000000000000000000000000000000000000001", 2**256 - 1],
    )
    sel = SELECTOR_SWAP_EXACT_ETH_FOR_TOKENS
    data = "0x" + sel[2:] + body.hex()
    tx = {"input": data, "value": hex(2 * 10**18)}
    ctx = decode_swap_context(tx, eth_usd=3000.0)
    assert ctx is not None
    assert ctx["direction"] == "buy"
    assert abs(float(ctx["estimated_volume_usd"]) - 6000.0) < 0.01


def test_heuristic_slippage_increases_with_size() -> None:
    a = heuristic_slippage_bps_py(500_000.0, 50_000_000.0)
    b = heuristic_slippage_bps_py(2_000_000.0, 50_000_000.0)
    assert b > a


def test_estimate_slippage_settings() -> None:
    s = OnchainSnifferSettings.model_construct(pool_tvl_usd_hint=50_000_000.0)
    v = estimate_slippage_bps(s, 1_000_000.0)
    assert v > 0
