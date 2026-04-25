from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AssetState = Literal[
    "unknown",
    "discovered",
    "quarantine",
    "research_only",
    "paper_allowed",
    "shadow_allowed",
    "live_candidate",
    "live_allowed",
    "blocked",
    "delisted",
    "suspended",
    "manual_review_required",
]
Actor = Literal["Philipp", "system"]
ExecutionMode = Literal["paper", "shadow", "live"]

STATE_ORDER: tuple[AssetState, ...] = (
    "unknown",
    "discovered",
    "quarantine",
    "research_only",
    "paper_allowed",
    "shadow_allowed",
    "live_candidate",
    "live_allowed",
)
TERMINAL_BLOCK_STATES: frozenset[AssetState] = frozenset(
    {"blocked", "delisted", "suspended", "manual_review_required"}
)


class AssetGovernanceRecord(BaseModel):
    asset_id: str
    symbol: str
    market_family: str
    product_type: str | None = None
    state: AssetState
    actor: str | None = None
    reason_de: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str
    expires_at: str | None = None
    risk_tier: str | None = None
    liquidity_tier: str | None = None
    data_quality_status: str = "data_unknown"
    liquidity_ok: bool = False
    strategy_evidence_ready: bool = False
    bitget_status_clear: bool = False

    @field_validator("asset_id", "symbol", "market_family", "product_type", "risk_tier", "liquidity_tier", mode="before")
    @classmethod
    def _normalize_upper(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper()

    @field_validator("reason_de", mode="before")
    @classmethod
    def _normalize_reason(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class AssetGovernanceTransition(BaseModel):
    asset_id: str
    symbol: str
    market_family: str
    product_type: str | None = None
    from_state: AssetState
    to_state: AssetState
    actor: Actor
    reason_de: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str
    expires_at: str | None = None
    risk_tier: str | None = None
    liquidity_tier: str | None = None
    data_quality_status: str


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    reasons: list[str]


def _state_index(state: AssetState) -> int:
    if state in TERMINAL_BLOCK_STATES:
        return -1
    return STATE_ORDER.index(state)


def can_transition(
    *,
    from_state: AssetState,
    to_state: AssetState,
    actor: str | None,
    reason_de: str,
    evidence_refs: list[str],
    data_quality_ok: bool,
    liquidity_ok: bool,
    strategy_evidence_ready: bool,
    bitget_status_clear: bool,
) -> TransitionDecision:
    reasons: list[str] = []
    if to_state in TERMINAL_BLOCK_STATES:
        return TransitionDecision(allowed=True, reasons=[])
    if from_state in TERMINAL_BLOCK_STATES:
        reasons.append("terminaler_block_state_kann_nicht_eskalieren")
    if _state_index(from_state) >= 0 and _state_index(to_state) >= 0:
        if _state_index(to_state) > _state_index(from_state) + 1:
            reasons.append("state_transition_ueberspringt_stufen")
    if to_state == "live_allowed":
        if actor != "Philipp":
            reasons.append("live_allowed_braucht_actor_philipp")
        if not reason_de:
            reasons.append("live_allowed_braucht_begruendung_de")
        if not evidence_refs:
            reasons.append("live_allowed_braucht_evidence_refs")
    if to_state in {"shadow_allowed", "live_candidate", "live_allowed"} and not data_quality_ok:
        reasons.append("datenqualitaet_unzureichend")
    if to_state in {"live_candidate", "live_allowed"} and not liquidity_ok:
        reasons.append("liquiditaetspruefung_fehlt")
    if to_state in {"live_candidate", "live_allowed"} and not strategy_evidence_ready:
        reasons.append("strategy_evidence_fehlt")
    if to_state in {"live_candidate", "live_allowed"} and not bitget_status_clear:
        reasons.append("bitget_status_unklar")
    return TransitionDecision(allowed=len(reasons) == 0, reasons=list(dict.fromkeys(reasons)))


def allows_real_orders(state: AssetState) -> bool:
    return state == "live_allowed"


def live_block_reasons(record: AssetGovernanceRecord) -> list[str]:
    reasons: list[str] = []
    if record.state in {
        "unknown",
        "discovered",
        "quarantine",
        "research_only",
        "paper_allowed",
        "shadow_allowed",
        "live_candidate",
        "blocked",
        "delisted",
        "suspended",
        "manual_review_required",
    }:
        reasons.append(f"state_{record.state}_nicht_live_freigegeben")
    if record.state == "live_allowed":
        if (record.actor or "") != "Philipp":
            reasons.append("live_allowed_ohne_philipp_actor")
        if not record.evidence_refs:
            reasons.append("live_allowed_ohne_evidence")
        if not record.reason_de:
            reasons.append("live_allowed_ohne_grund")
    if record.data_quality_status != "data_ok":
        reasons.append("datenqualitaet_nicht_ok")
    if not record.liquidity_ok:
        reasons.append("liquiditaet_nicht_ok")
    if not record.strategy_evidence_ready:
        reasons.append("strategy_evidence_nicht_ok")
    if not record.bitget_status_clear:
        reasons.append("bitget_status_nicht_klar")
    return list(dict.fromkeys(reasons))


def german_label_for_state(state: AssetState) -> str:
    mapping = {
        "live_allowed": "Live erlaubt",
        "shadow_allowed": "Nur Shadow",
        "paper_allowed": "Nur Paper",
        "quarantine": "In Quarantaene",
        "blocked": "Blockiert",
        "manual_review_required": "Manuelle Pruefung noetig",
    }
    return mapping.get(state, state.replace("_", " "))


def scorecard_payload(records: list[AssetGovernanceRecord]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for record in records:
        reasons = live_block_reasons(record)
        payload.append(
            {
                "symbol": record.symbol,
                "status_label_de": german_label_for_state(record.state),
                "warum_blockiert": reasons,
                "evidence_fehlt": [] if record.evidence_refs else ["evidence_refs"],
                "live_erlaubt": allows_real_orders(record.state) and len(reasons) == 0,
            }
        )
    return payload


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
