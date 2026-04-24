"""
Begruendungspaket fuer Apex-Audit-Ledger: deterministische Fingerabdruecke fuer
Signal, KI-/War-Room-Artefakte, Risk-Sign-Off (manipulationssichere Kette s. audit_ledger).

Keine Roh-LLM-Prompts: nur redigierte, strukturelle Bloecke.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from shared_py.audit_ledger_chain import canonical_json_bytes
from shared_py.observability.execution_forensic import redact_nested_mapping


def content_sha256_hex(obj: Any) -> str:
    """SHA-256-Hex ueber sortierten JSON, fuer fachliche Beweiskette (nicht HMAC)."""
    if isinstance(obj, (dict, list)):
        b = canonical_json_bytes(obj)
    else:
        b = canonical_json_bytes({"_v": str(obj)[:8_000]})
    return hashlib.sha256(b).hexdigest()


def build_ledger_decision_package(
    *,
    market_event_json: dict[str, Any] | None,
    war_room: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Baut ein signierbares Paket (Vor-Redaction bereits in ledger_repository, hier tiefer
    abgesichert): Signal, KI-/Operator-Erklaerung, Risk-Block.
    """
    me = copy.deepcopy(market_event_json) if isinstance(market_event_json, dict) else {}
    me = redact_nested_mapping(me, max_depth=7)
    wr = copy.deepcopy(war_room) if isinstance(war_room, dict) else {}
    wr = redact_nested_mapping(wr, max_depth=8)

    signal_block: dict[str, Any] = {
        "symbol": me.get("symbol") or (me.get("market_event") or {}).get("symbol"),
        "timeframe": me.get("timeframe"),
        "signal_id": str(me.get("signal_id") or me.get("signal", {}).get("signal_id") or "")
        or None,
        "direction_hint": str(me.get("direction") or "")[:32] or None,
        "market_context_keys": sorted([str(x) for x in me.keys() if isinstance(x, str)][:32]),
    }
    wr_op = wr.get("operator_explain")
    if not isinstance(wr_op, dict):
        wr_op = {}
    llm_block: dict[str, Any] = {
        "version": wr.get("version"),
        "consensus_status": wr.get("consensus_status"),
        "final_signal_action": wr.get("final_signal_action"),
        "operator_explain_schema": wr_op.get("schema_version")
        or wr_op.get("execution_authority"),
        "operator_explain_excerpt": str(wr_op.get("explanation_de", ""))[:4_000],
    }
    risk_block: dict[str, Any] = {
        "risk_hard_veto": wr.get("risk_hard_veto"),
        "consensus_status": wr.get("consensus_status"),
        "signal_generation_aborted": wr.get("signal_generation_aborted"),
        "final_signal_action": wr.get("final_signal_action"),
        "foundation_model_audit": (
            (wr.get("foundation_model_audit") or {}) if isinstance(wr.get("foundation_model_audit"), dict) else {}
        )
        or {},
    }

    return {
        "decision_package_version": "1",
        "signal_fingerprint_sha256": content_sha256_hex(signal_block),
        "llm_and_consensus_fingerprint_sha256": content_sha256_hex(llm_block),
        "risk_signoff_fingerprint_sha256": content_sha256_hex(risk_block),
        "signal_ledger_slice": signal_block,
        "llm_ledger_slice": llm_block,
        "risk_ledger_slice": {
            "risk_hard_veto": risk_block.get("risk_hard_veto"),
            "consensus_status": risk_block.get("consensus_status"),
            "final_signal_action": risk_block.get("final_signal_action"),
        },
    }
