"""
Golden Record (Trade-Lifecycle) aus aggregierter Forensik-Timeline (Prompt 68).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from shared_py.observability.execution_forensic import redact_nested_mapping


def _m(o: Any) -> dict[str, Any]:
    return o if isinstance(o, dict) else {}


def _excerpt(s: str | None, n: int = 800) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    if len(t) > n:
        return t[: n - 3] + "..."
    return t or None


@dataclass
class TradeLifecycleAuditRecord:
    """Normalisiert Signal, KI, Risiko, Boerse — serialisierbar als golden_record."""

    execution_id: str
    signal_id: str | None
    recorded_ts_ms: int
    phases: dict[str, Any] = field(default_factory=dict)
    signal_path_summary_ref: dict[str, Any] | None = None
    schema_version: str = "trade_lifecycle_golden_v1"

    def to_golden_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "execution_id": str(self.execution_id),
            "signal_id": str(self.signal_id) if self.signal_id else None,
            "recorded_ts_ms": int(self.recorded_ts_ms),
            "phases": self.phases,
        }
        if self.signal_path_summary_ref is not None:
            out["signal_path_summary_ref"] = self.signal_path_summary_ref
        return out

    @classmethod
    def from_timeline(
        cls,
        timeline: dict[str, Any],
    ) -> TradeLifecycleAuditRecord:
        ex = str(timeline.get("execution_id") or "")
        cor = _m(timeline.get("correlation"))
        sig_id = cor.get("signal_id")
        if sig_id is not None:
            sig_id = str(sig_id)

        sc = _m(timeline.get("signal_context"))
        raw_snap = sc.get("source_snapshot_json")
        ssnap: dict[str, Any] = raw_snap if isinstance(raw_snap, dict) else {}

        micro: dict[str, Any] = {}
        if isinstance(ssnap, dict):
            for key in (
                "microstructure",
                "orderbook_top",
                "orderbook_imbalance",
                "vpin_0_1",
                "spread_bps",
                "funding_annualized",
                "correlation_chain",
                "candles_tail_meta",
            ):
                if key in ssnap and ssnap[key] is not None:
                    v = ssnap[key]
                    micro[key] = redact_nested_mapping(
                        v if isinstance(v, dict | list) else v,
                        max_depth=3,
                    )

        phase_signal: dict[str, Any] = {
            "core": {
                "signal_id": sc.get("signal_id"),
                "symbol": sc.get("symbol"),
                "timeframe": sc.get("timeframe"),
                "direction": sc.get("direction"),
                "trade_action": sc.get("trade_action"),
                "playbook_id": sc.get("playbook_id"),
                "meta_trade_lane": sc.get("meta_trade_lane"),
                "decision_state": sc.get("decision_state"),
                "analysis_ts_ms": sc.get("analysis_ts_ms"),
            },
            "microstructure": redact_nested_mapping(micro, max_depth=4),
        }

        _elm = sc.get("explain_long_md")
        eld = str(_elm or "") if _elm is not None else None
        conf_01: str | int | float | None = None
        rj0 = sc.get("reasons_json")
        if isinstance(rj0, str):
            try:
                import json

                rj0 = json.loads(rj0)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                rj0 = {}
        if not isinstance(rj0, dict):
            rj0 = {}
        spec0 = rj0.get("specialists")
        if isinstance(spec0, dict):
            for _block in spec0.values():
                if not isinstance(_block, dict):
                    continue
                prp = _block.get("proposal")
                if isinstance(prp, dict) and prp.get("confidence_0_1") is not None:
                    conf_01 = prp.get("confidence_0_1")
                    break
        phase_ai: dict[str, Any] = {
            "explain_short": sc.get("explain_short"),
            "explain_long_md_excerpt": _excerpt(eld),
        }
        if conf_01 is not None:
            phase_ai["confidence_0_1"] = conf_01
        sps = timeline.get("signal_path_summary")
        if isinstance(sps, dict) and sps:
            phase_ai["specialist_forensic_summary"] = {
                "schema_version": sps.get("schema_version"),
                "decision_control_flow": (sps.get("decision_control_flow") or {})
                if isinstance(sps.get("decision_control_flow"), dict)
                else {},
            }

        rs = timeline.get("risk_snapshot")
        rs = rs if isinstance(rs, dict) else {}
        detail = _m(rs.get("detail_json"))
        dr = detail.get("decision_reason") or detail.get("primary_reason")
        phase_risk: dict[str, Any] = {
            "execution_decision_id": rs.get("execution_decision_id"),
            "trade_action": rs.get("trade_action"),
            "decision_reason": (str(dr or ""))[:400] or None,
            "metrics": redact_nested_mapping(
                _m(rs.get("metrics_json")),
                max_depth=4,
            ),
        }

        dec = _m(timeline.get("decision"))
        phase_risk["signoff_from_decision"] = {
            "leverage": dec.get("leverage"),
            "approved_7x": dec.get("approved_7x"),
            "order_type": dec.get("order_type"),
            "qty_base": (
                str(dec["qty_base"])
                if dec.get("qty_base") is not None
                else None
            ),
        }
        pjl = _m(dec.get("payload_json"))
        if pjl:
            phase_risk["decision_payload_excerpt"] = redact_nested_mapping(
                pjl, max_depth=2
            )

        orders: list[dict[str, Any]] = []
        for o in timeline.get("orders") or []:
            if not isinstance(o, dict):
                continue
            orders.append(
                {
                    "internal_order_id": o.get("internal_order_id"),
                    "exchange_order_id": o.get("exchange_order_id"),
                    "client_oid": o.get("client_oid"),
                    "side": o.get("side"),
                    "status": o.get("status"),
                    "order_type": o.get("order_type"),
                    "margin_mode": o.get("margin_mode"),
                }
            )

        fills: list[dict[str, Any]] = []
        for f in timeline.get("fills") or []:
            if not isinstance(f, dict):
                continue
            price = f.get("price")
            fills.append(
                {
                    "exchange_order_id": f.get("exchange_order_id"),
                    "exchange_trade_id": f.get("exchange_trade_id"),
                    "price": str(price) if price is not None else None,
                    "size": str(f.get("size")) if f.get("size") is not None else None,
                    "side": f.get("side"),
                    "fee": str(f.get("fee")) if f.get("fee") is not None else None,
                    "is_maker": f.get("is_maker"),
                }
            )

        phase_ex: dict[str, Any] = {
            "orders": orders,
            "fills": fills,
        }

        sps_ref = None
        sps0 = timeline.get("signal_path_summary")
        if isinstance(sps0, dict):
            sps_ref = {
                "schema_version": sps0.get("schema_version"),
            }

        ts_ms = int(time.time() * 1000)
        return cls(
            execution_id=ex,
            signal_id=sig_id,
            recorded_ts_ms=ts_ms,
            phases={
                "signal": phase_signal,
                "ai_rationale": phase_ai,
                "risk_signoff": phase_risk,
                "exchange": phase_ex,
            },
            signal_path_summary_ref=sps_ref,
        )


def build_golden_record_from_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    """Baut den persistierbaren JSON-Blob (ohne Hash-Felder)."""
    return TradeLifecycleAuditRecord.from_timeline(timeline).to_golden_dict()
