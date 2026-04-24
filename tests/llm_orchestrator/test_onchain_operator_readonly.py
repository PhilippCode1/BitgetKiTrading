from __future__ import annotations

from llm_orchestrator.knowledge.onchain_macro import (
    build_readonly_onchain_text,
    merge_fetched_onchain_into_context,
)
from llm_orchestrator.knowledge.retrieval import (
    format_operator_readonly_pro_symbol,
    PLACEHOLDER_NO_ONCHAIN_MACRO,
)


def test_format_operator_readonly_contains_onchain_lines() -> None:
    ctx = {
        "symbol": "BTCUSDT",
        "onchain_context": {
            "onchain_whale_pressure_0_1": 0.2,
            "recent_onchain_whale_events_json": [
                {
                    "event_name": "ONCHAIN_WHALE_DETECTION",
                    "source_chain": "ethereum",
                    "dex": "binance_router_mock",
                    "token_pair": "WETH→USDC",
                    "direction": "sell",
                    "estimated_volume_usd": 500_000.0,
                }
            ],
        },
        "onchain_macro": {
            "lines_de": ["de line"],
            "lines_en": [
                "On-Chain: Whale inflow / heavy sell-side activity detected: est. 500,000 USD notional, "
                "WETH→USDC to Binance (router label) (ethereum) [direction=sell]."
            ],
        },
    }
    out = format_operator_readonly_pro_symbol(ctx, max_total_chars=20_000)
    assert "onchain_macro" in out
    assert "On-Chain" in out
    assert "Whale" in out
    assert "Binance" in out
    assert PLACEHOLDER_NO_ONCHAIN_MACRO not in out


def test_build_readonly_onchain_text_from_context_only() -> None:
    ctx = {
        "onchain_context": {
            "recent_onchain_whale_events_json": [
                {
                    "source_chain": "ethereum",
                    "dex": "uniswap_v2",
                    "token_pair": "WETH→USDC",
                    "direction": "buy",
                    "estimated_volume_usd": 1_200_000.0,
                }
            ],
        }
    }
    t = build_readonly_onchain_text(ctx)
    assert "On-Chain" in t
    assert "Whale" in t or "Kauf" in t


def test_merge_preserves_higher_whale_pressure() -> None:
    t = merge_fetched_onchain_into_context(
        {"onchain_context": {"onchain_whale_pressure_0_1": 0.5}},
        {
            "onchain_context": {
                "onchain_whale_pressure_0_1": 0.2,
                "recent_onchain_whale_events_json": [{"estimated_volume_usd": 1.0}],
            }
        },
    )
    assert float(t["onchain_context"]["onchain_whale_pressure_0_1"]) == 0.5
