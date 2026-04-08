from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.structured_market_context import (
    assess_structured_market_context,
    merge_live_reasons_into_risk_governor,
    refine_structured_market_context_for_playbook,
)


def _settings(**overrides: object) -> SimpleNamespace:
    base = dict(
        structured_market_context_enabled=True,
        smc_news_decay_half_life_minutes=120.0,
        smc_surprise_directional_threshold_0_1=0.58,
        smc_surprise_live_throttle_threshold_0_1=0.52,
        smc_composite_shrink_min_0_1=0.88,
        smc_hard_event_veto_enabled=False,
        smc_hard_event_veto_surprise_0_1=0.82,
        smc_enable_structural_break_boost=True,
        smc_playbook_news_sensitive_surprise_mult=1.1,
        smc_playbook_trend_surprise_mult=0.96,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_disabled_short_circuits_with_flag() -> None:
    out = assess_structured_market_context(
        news_row={"title": "fomc"},
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(structured_market_context_enabled=False),
    )
    assert out.get("disabled") is True
    assert out.get("composite_effective_factor_0_1") == 1.0


def test_no_news_row_adds_annotation_only() -> None:
    out = assess_structured_market_context(
        news_row=None,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(smc_surprise_directional_threshold_0_1=0.99),
    )
    assert "no_news_row_context" in (out.get("annotation_only_reasons_json") or [])


def test_bearish_macro_vs_long_soft_conflict_at_lower_threshold() -> None:
    news = {
        "relevance_score": 100,
        "sentiment": "baerisch",
        "impact_window": "sofort",
        "title": "fomc raises rates sharply",
        "published_ts_ms": 1_700_000_000_000,
    }
    out = assess_structured_market_context(
        news_row=news,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(smc_surprise_directional_threshold_0_1=0.4),
    )
    assert "macro" in (out.get("facets_active_json") or [])
    assert "context_event_bearish_vs_long" in (out.get("conflict_codes_json") or [])
    assert "context_technical_vs_event_long" in (out.get("deterministic_rejection_soft_json") or [])
    assert float(out.get("composite_effective_factor_0_1") or 1.0) < 1.0


def test_decay_reduces_surprise_over_time() -> None:
    news = {
        "relevance_score": 100,
        "sentiment": "baerisch",
        "impact_window": "mittel",
        "title": "fed outlook",
        "published_ts_ms": 1_700_000_000_000,
    }
    fresh = assess_structured_market_context(
        news_row=news,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(smc_news_decay_half_life_minutes=60.0),
    )
    aged = assess_structured_market_context(
        news_row=news,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000 + 120 * 60_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(smc_news_decay_half_life_minutes=60.0),
    )
    assert float(aged["surprise_score_0_1"]) < float(fresh["surprise_score_0_1"])


def test_live_escalation_tag_when_surprise_above_live_threshold() -> None:
    news = {
        "relevance_score": 95,
        "sentiment": "baerisch",
        "impact_window": "sofort",
        "title": "fomc surprise hike",
        "published_ts_ms": 1_700_000_000_000,
    }
    out = assess_structured_market_context(
        news_row=news,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(
            smc_surprise_directional_threshold_0_1=0.99,
            smc_surprise_live_throttle_threshold_0_1=0.35,
        ),
    )
    assert "context_live_event_surprise_escalation" in (
        out.get("live_execution_block_reasons_json") or []
    )


def test_optional_hard_veto_long_bearish() -> None:
    news = {
        "relevance_score": 90,
        "sentiment": "baerisch",
        "impact_window": "sofort",
        "title": "black swan macro",
        "published_ts_ms": 1_700_000_000_000,
    }
    out = assess_structured_market_context(
        news_row=news,
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="long",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(
            smc_hard_event_veto_enabled=True,
            smc_hard_event_veto_surprise_0_1=0.35,
        ),
    )
    assert "context_hard_event_veto_long" in (out.get("deterministic_rejection_hard_json") or [])


def test_playbook_news_shock_adds_live_escalation() -> None:
    base = assess_structured_market_context(
        news_row={
            "relevance_score": 100,
            "sentiment": "bullisch",
            "impact_window": "sofort",
            "title": "fomc emergency headline",
            "published_ts_ms": 1_700_000_000_000,
        },
        symbol="BTCUSDT",
        market_family="futures",
        proposed_direction="short",
        analysis_ts_ms=1_700_000_000_000,
        structure_events=[],
        primary_feature={},
        settings=_settings(
            smc_surprise_directional_threshold_0_1=0.99,
            smc_surprise_live_throttle_threshold_0_1=0.45,
            smc_playbook_news_sensitive_surprise_mult=1.2,
        ),
    )
    refined = refine_structured_market_context_for_playbook(
        base,
        playbook_family="news_shock",
        settings=_settings(smc_surprise_live_throttle_threshold_0_1=0.45),
    )
    assert "context_playbook_news_shock_live_escalation" in (
        refined.get("live_execution_block_reasons_json") or []
    )


def test_merge_live_reasons_into_risk_governor_appends_unique() -> None:
    rg: dict = {"live_execution_block_reasons_json": ["existing"]}
    smc = {"live_execution_block_reasons_json": ["context_live_event_surprise_escalation", "existing"]}
    merge_live_reasons_into_risk_governor(rg, smc)
    assert rg["live_execution_block_reasons_json"] == [
        "existing",
        "context_live_event_surprise_escalation",
    ]
