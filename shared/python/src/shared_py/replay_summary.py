from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

REPLAY_SUMMARY_VERSION = "private-replay-summary-v1"
REQUIRED_REPLAY_STEPS = (
    "signal",
    "risk",
    "exchange",
)


@dataclass(frozen=True)
class ReplaySummary:
    replay_sufficient: bool
    missing_steps: list[str]
    warnings: list[str]
    summary_text_de: str


def build_replay_summary(trace: dict[str, Any]) -> dict[str, Any]:
    steps = trace.get("steps")
    if not isinstance(steps, dict):
        steps = {}

    missing: list[str] = []
    warnings: list[str] = []
    for step in REQUIRED_REPLAY_STEPS:
        value = steps.get(step)
        if not isinstance(value, dict) or not value:
            missing.append(step)

    risk_step = steps.get("risk") if isinstance(steps.get("risk"), dict) else {}
    if risk_step and not risk_step.get("reason_codes"):
        missing.append("risk.reason_codes")

    exchange_step = steps.get("exchange") if isinstance(steps.get("exchange"), dict) else {}
    if exchange_step and not exchange_step.get("exchange_truth_status"):
        missing.append("exchange.exchange_truth_status")

    if trace.get("llm_explanation_only") is True:
        warnings.append("llm_explanation_not_audit_truth")

    replay_sufficient = not missing
    if replay_sufficient:
        text = "Replay ist ausreichend: Signal-, Risk- und Exchange-Schritte sind vorhanden."
    else:
        text = "Replay ist unvollstaendig: fehlende Schritte " + ", ".join(missing) + "."

    summary = ReplaySummary(
        replay_sufficient=replay_sufficient,
        missing_steps=list(dict.fromkeys(missing)),
        warnings=warnings,
        summary_text_de=text,
    )
    return {
        "schema_version": REPLAY_SUMMARY_VERSION,
        **asdict(summary),
    }
