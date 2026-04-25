from __future__ import annotations

from shared_py.bitget.asset_governance import (
    AssetGovernanceRecord,
    can_transition,
    live_block_reasons,
)


def _record(**overrides: object) -> AssetGovernanceRecord:
    payload: dict[str, object] = {
        "asset_id": "ASSET-BTCUSDT",
        "symbol": "BTCUSDT",
        "market_family": "FUTURES",
        "product_type": "USDT-FUTURES",
        "state": "live_allowed",
        "actor": "Philipp",
        "reason_de": "Owner-Freigabe fuer Live-Betrieb",
        "evidence_refs": ["report://shadow_burn_in"],
        "created_at": "2026-04-25T16:00:00+00:00",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "liquidity_tier": "LIQUIDITY_TIER_1",
        "data_quality_status": "data_ok",
        "liquidity_ok": True,
        "strategy_evidence_ready": True,
        "bitget_status_clear": True,
    }
    payload.update(overrides)
    return AssetGovernanceRecord.model_validate(payload)


def test_discovered_blocks_live() -> None:
    assert "state_discovered_nicht_live_freigegeben" in live_block_reasons(_record(state="discovered"))


def test_quarantine_blocks_live() -> None:
    assert "state_quarantine_nicht_live_freigegeben" in live_block_reasons(_record(state="quarantine"))


def test_paper_allowed_blocks_real_orders() -> None:
    assert "state_paper_allowed_nicht_live_freigegeben" in live_block_reasons(_record(state="paper_allowed"))


def test_shadow_allowed_blocks_real_orders() -> None:
    assert "state_shadow_allowed_nicht_live_freigegeben" in live_block_reasons(_record(state="shadow_allowed"))


def test_live_candidate_blocks_real_orders() -> None:
    assert "state_live_candidate_nicht_live_freigegeben" in live_block_reasons(_record(state="live_candidate"))


def test_live_allowed_without_actor_blocks() -> None:
    reasons = live_block_reasons(_record(actor=None))
    assert "live_allowed_ohne_philipp_actor" in reasons


def test_live_allowed_without_evidence_blocks() -> None:
    reasons = live_block_reasons(_record(evidence_refs=[]))
    assert "live_allowed_ohne_evidence" in reasons


def test_delisted_blocks() -> None:
    assert "state_delisted_nicht_live_freigegeben" in live_block_reasons(_record(state="delisted"))


def test_suspended_blocks() -> None:
    assert "state_suspended_nicht_live_freigegeben" in live_block_reasons(_record(state="suspended"))


def test_unknown_blocks() -> None:
    assert "state_unknown_nicht_live_freigegeben" in live_block_reasons(_record(state="unknown"))


def test_transition_does_not_skip_discovered_to_live_allowed() -> None:
    out = can_transition(
        from_state="discovered",
        to_state="live_allowed",
        actor="Philipp",
        reason_de="Direktfreigabe",
        evidence_refs=["e1"],
        data_quality_ok=True,
        liquidity_ok=True,
        strategy_evidence_ready=True,
        bitget_status_clear=True,
    )
    assert out.allowed is False
    assert "state_transition_ueberspringt_stufen" in out.reasons
