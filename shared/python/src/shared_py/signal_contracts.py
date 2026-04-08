"""
Gemeinsame Konstanten und Typ-Aliase fuer Signal Engine V1 (Event-Payload, API).
"""

from __future__ import annotations

from typing import Literal

SignalDirection = Literal["long", "short", "neutral"]
SignalClass = Literal["mikro", "kern", "gross", "warnung"]
DecisionState = Literal["accepted", "downgraded", "rejected"]
TradeAction = Literal["allow_trade", "do_not_trade"]
PlaybookDecisionMode = Literal["selected", "playbookless"]

# Meta-Entscheidung Prompt 22 — Lane unabhaengig vom binaeren trade_action (Execution).
MetaTradeLane = Literal["do_not_trade", "shadow_only", "paper_only", "candidate_for_live"]
META_TRADE_LANE_VALUES: tuple[str, ...] = (
    "do_not_trade",
    "shadow_only",
    "paper_only",
    "candidate_for_live",
)

# Finaler Meta-Entscheidungsaktionsraum (Kernel-Output, unabhaengig vom binaeren trade_action-Legacy).
MetaDecisionAction = Literal[
    "do_not_trade",
    "allow_trade_candidate",
    "candidate_for_live",
    "operator_release_pending",
    "blocked_by_policy",
]
META_DECISION_ACTION_VALUES: tuple[str, ...] = (
    "do_not_trade",
    "allow_trade_candidate",
    "candidate_for_live",
    "operator_release_pending",
    "blocked_by_policy",
)

# Trend aus Feature-Engine features.candle_features.trend_dir
TrendDirInt = Literal[-1, 0, 1]

SIGNAL_EVENT_SCHEMA_VERSION = "1.0"
