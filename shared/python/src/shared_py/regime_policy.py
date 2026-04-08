from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field

RegimeState = Literal[
    "trend",
    "mean_reverting",
    "compression",
    "expansion",
    "news_driven",
    "shock",
    "low_liquidity",
    "delivery_sensitive",
    "funding_skewed",
    "session_transition",
    "range_grind",
]
RegimeTransitionState = Literal[
    "stable",
    "entering",
    "switch_confirmed",
    "sticky_hold",
    "switch_immediate",
]

REGIME_ONTOLOGY_VERSION = "1.0"
REGIME_ROUTING_POLICY_VERSION = "1.0"
REGIME_STATE_VALUES: tuple[str, ...] = (
    "trend",
    "mean_reverting",
    "compression",
    "expansion",
    "news_driven",
    "shock",
    "low_liquidity",
    "delivery_sensitive",
    "funding_skewed",
    "session_transition",
    "range_grind",
)
REGIME_TRANSITION_STATE_VALUES: tuple[str, ...] = (
    "stable",
    "entering",
    "switch_confirmed",
    "sticky_hold",
    "switch_immediate",
)


class RegimePlaybookPolicy(BaseModel):
    regime_state: RegimeState
    allowed_playbook_families: list[str] = Field(default_factory=list)
    blocked_playbook_families: list[str] = Field(default_factory=list)
    no_trade_by_default: bool = False
    specialist_bias: list[str] = Field(default_factory=list)


REGIME_PLAYBOOK_POLICIES: tuple[RegimePlaybookPolicy, ...] = (
    RegimePlaybookPolicy(
        regime_state="trend",
        allowed_playbook_families=["trend_continuation", "pullback", "breakout"],
        blocked_playbook_families=["mean_reversion", "range_rotation"],
        specialist_bias=["family_specialists", "regime_specialists", "playbook_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="mean_reverting",
        allowed_playbook_families=["mean_reversion", "range_rotation", "liquidity_sweep"],
        blocked_playbook_families=["trend_continuation", "breakout"],
        specialist_bias=["mean_reversion_specialists", "microstructure_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="compression",
        allowed_playbook_families=["volatility_compression_expansion", "breakout", "time_window_effect"],
        blocked_playbook_families=["carry_funding"],
        specialist_bias=["regime_specialists", "playbook_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="expansion",
        allowed_playbook_families=["breakout", "trend_continuation", "session_open"],
        blocked_playbook_families=["range_rotation"],
        specialist_bias=["trend_specialists", "execution_risk"],
    ),
    RegimePlaybookPolicy(
        regime_state="news_driven",
        allowed_playbook_families=["news_shock", "time_window_effect"],
        blocked_playbook_families=["range_rotation", "mean_reversion"],
        specialist_bias=["news_specialists", "risk_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="shock",
        allowed_playbook_families=["news_shock"],
        blocked_playbook_families=[
            "trend_continuation",
            "breakout",
            "pullback",
            "range_rotation",
            "mean_reversion",
            "carry_funding",
        ],
        no_trade_by_default=True,
        specialist_bias=["shock_specialists", "risk_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="low_liquidity",
        allowed_playbook_families=["liquidity_sweep"],
        blocked_playbook_families=[
            "trend_continuation",
            "breakout",
            "pullback",
            "range_rotation",
            "carry_funding",
            "session_open",
        ],
        no_trade_by_default=True,
        specialist_bias=["microstructure_specialists", "risk_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="delivery_sensitive",
        allowed_playbook_families=["time_window_effect", "carry_funding"],
        blocked_playbook_families=["breakout", "trend_continuation", "pullback"],
        no_trade_by_default=True,
        specialist_bias=["family_specialists", "risk_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="funding_skewed",
        allowed_playbook_families=["carry_funding", "time_window_effect", "trend_continuation"],
        blocked_playbook_families=["range_rotation"],
        specialist_bias=["family_specialists", "carry_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="session_transition",
        allowed_playbook_families=["session_open", "time_window_effect", "breakout"],
        blocked_playbook_families=["carry_funding"],
        specialist_bias=["session_specialists", "playbook_specialists"],
    ),
    RegimePlaybookPolicy(
        regime_state="range_grind",
        allowed_playbook_families=["range_rotation", "mean_reversion"],
        blocked_playbook_families=["trend_continuation", "breakout"],
        specialist_bias=["mean_reversion_specialists", "regime_specialists"],
    ),
)

_POLICY_BY_STATE = {item.regime_state: item for item in REGIME_PLAYBOOK_POLICIES}
REGIME_POLICY_HASH = hashlib.sha256(
    json.dumps(
        {
            "ontology_version": REGIME_ONTOLOGY_VERSION,
            "routing_policy_version": REGIME_ROUTING_POLICY_VERSION,
            "policies": [item.model_dump(mode="json") for item in REGIME_PLAYBOOK_POLICIES],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def get_regime_playbook_policy(regime_state: str | None) -> RegimePlaybookPolicy | None:
    if not regime_state:
        return None
    return _POLICY_BY_STATE.get(str(regime_state).strip())


def regime_policy_descriptor() -> dict[str, object]:
    return {
        "ontology_version": REGIME_ONTOLOGY_VERSION,
        "routing_policy_version": REGIME_ROUTING_POLICY_VERSION,
        "policy_hash": REGIME_POLICY_HASH,
        "regime_states": list(REGIME_STATE_VALUES),
        "transition_states": list(REGIME_TRANSITION_STATE_VALUES),
        "policies": [item.model_dump(mode="json") for item in REGIME_PLAYBOOK_POLICIES],
    }
