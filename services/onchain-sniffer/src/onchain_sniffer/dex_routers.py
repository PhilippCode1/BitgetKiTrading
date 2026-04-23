"""Bekannte DEX-Router (Ethereum Mainnet) — Lowercase fuer Vergleich."""

from __future__ import annotations

# Uniswap V2 Router02
UNISWAP_V2_ROUTER = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"
# Uniswap V3 SwapRouter
UNISWAP_V3_SWAPROUTER = "0xe592427a0aece92de3edee1f18e0157c05861564"
# Uniswap V3 SwapRouter02 (Universal-ish)
SWAPROUTER_02 = "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45"
# Universal Router
UNIVERSAL_ROUTER = "0x3fc91a3afd70395cd496c647d5a6cc9d4b2fad0e"

ETH_MAINNET_DEX_ROUTERS: frozenset[str] = frozenset(
    {
        UNISWAP_V2_ROUTER,
        UNISWAP_V3_SWAPROUTER,
        SWAPROUTER_02,
        UNIVERSAL_ROUTER,
    }
)

WETH_MAINNET = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

SELECTOR_SWAP_EXACT_ETH_FOR_TOKENS = "0x7ff36ab5"
SELECTOR_SWAP_EXACT_TOKENS_FOR_ETH = "0x18cbafe5"
SELECTOR_SWAP_EXACT_TOKENS_FOR_TOKENS = "0x38ed1739"
SELECTOR_EXACT_INPUT_SINGLE = "0x414bf389"  # exactInputSingle (V3 pool)
