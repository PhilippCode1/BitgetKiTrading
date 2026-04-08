from __future__ import annotations

from uuid import uuid4

from signal_engine.explain.risk_warnings import build_risk_warnings
from signal_engine.explain.schemas import ExplainInput


def _base_signal(**kwargs: object) -> dict:
    row = {
        "signal_id": str(uuid4()),
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "analysis_ts_ms": 1_800_000_000_000,
        "direction": "long",
        "signal_strength_0_100": 60,
        "probability_0_1": 0.5,
        "reward_risk_ratio": 2.0,
    }
    row.update(kwargs)
    return row


def _inp(
    signal_row: dict,
    *,
    pf: dict | None,
    drawings: list | None = None,
    features_by_tf: dict | None = None,
    news: dict | None = None,
    last_close: float | None = 100.0,
    events: list | None = None,
) -> ExplainInput:
    return ExplainInput(
        signal_row=signal_row,
        structure_state=None,
        structure_events=events or [],
        primary_feature=pf,
        features_by_tf=features_by_tf
        or {"1m": None, "5m": None, "15m": None, "1H": None, "4H": None},
        drawings=drawings or [],
        news_row=news,
        last_close=last_close,
    )


def test_stale_data_warning(signal_settings) -> None:
    sig = _base_signal()
    pf = {"computed_ts_ms": 1_799_000_000_000, "atr_14": 1.0}
    w = build_risk_warnings(_inp(sig, pf=pf), signal_settings)
    codes = {x["code"] for x in w}
    assert "STALE_DATA" in codes


def test_stop_too_tight(signal_settings) -> None:
    sig = _base_signal()
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 10.0}
    drawings = [
        {"type": "stop_zone", "geometry": {"price_low": "99.9", "price_high": "100.1"}},
    ]
    w = build_risk_warnings(
        _inp(sig, pf=pf, drawings=drawings, last_close=100.0), signal_settings
    )
    assert any(x["code"] == "STOP_TOO_TIGHT_FOR_ATR" for x in w)


def test_conflict_high_tf(signal_settings) -> None:
    sig = _base_signal(direction="long")
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 5.0}
    fmap = {
        "1m": {"trend_dir": 1},
        "5m": {"trend_dir": 1},
        "15m": {"trend_dir": 1},
        "1H": {"trend_dir": -1},
        "4H": {"trend_dir": 0},
    }
    w = build_risk_warnings(_inp(sig, pf=pf, features_by_tf=fmap), signal_settings)
    assert any(x["code"] == "CONFLICT_HIGH_TF" for x in w)


def test_false_breakout_risk(signal_settings) -> None:
    sig = _base_signal()
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 5.0}
    ev = [{"type": "FALSE_BREAKOUT", "event_id": "e1", "ts_ms": 1}]
    w = build_risk_warnings(_inp(sig, pf=pf, events=ev), signal_settings)
    assert any(x["code"] == "BREAKOUT_FALSE_RISK" for x in w)


def test_low_rr(signal_settings) -> None:
    sig = _base_signal(reward_risk_ratio=0.5)
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 5.0}
    w = build_risk_warnings(_inp(sig, pf=pf), signal_settings)
    assert any(x["code"] == "LOW_RR" for x in w)


def test_news_shock_against_long(signal_settings) -> None:
    sig = _base_signal(direction="long")
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 5.0}
    news = {"relevance_score": 70.0, "sentiment": -0.5}
    w = build_risk_warnings(_inp(sig, pf=pf, news=news), signal_settings)
    assert any(x["code"] == "NEWS_SHOCK_AGAINST" for x in w)


def test_regime_shock_warning(signal_settings) -> None:
    sig = _base_signal(
        market_regime="shock",
        regime_bias="short",
        regime_confidence_0_1=0.91,
    )
    pf = {"computed_ts_ms": sig["analysis_ts_ms"], "atr_14": 5.0}
    w = build_risk_warnings(_inp(sig, pf=pf), signal_settings)
    assert any(x["code"] == "REGIME_SHOCK" for x in w)
