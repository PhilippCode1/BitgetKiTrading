"""
Strukturierte Operator-Information fuer Telegram/Outbox (keine Strategie-Mutation).

- Keine Secrets, keine rohen LLM-Prompts, keine vollstaendigen internen Snapshots.
- Kanonisches Textlayout fuer alert-engine Outbox (Feld payload.text).
"""

from __future__ import annotations

import re
from typing import Any

# Schluessel die nie in Telegram-Payloads landen duerfen (Substring-Match auf flache Keys)
_REDACT_KEY_SUBSTRINGS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "passphrase",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "prompt",
    "system_prompt",
    "messages_json",
    "raw_llm",
    "chat_id",
    "user_id",
    "username",
    "email",
    "phone",
)

_INTEL_KIND_TO_LABEL: dict[str, str] = {
    "pre_trade_rationale": "PRE-TRADE",
    "release_pending": "FREIGABE AUSSTEHEND",
    "trade_open": "TRADE OPEN",
    "trade_close": "TRADE CLOSE",
    "exit_rationale": "EXIT",
    "incident": "INCIDENT",
    "kill_switch": "KILL-SWITCH",
    "safety_latch": "SAFETY-LATCH",
    "strategy_intent": "STRATEGIE / INTENT",
    "no_trade": "NO-TRADE",
    "plan_summary": "PLAN (Freigabe)",
    "risk_notice": "RISK",
    "fill": "FILL",
    "exit_result": "EXIT",
    "post_trade_review": "POST-TRADE",
    "execution_update": "EXECUTION",
}


def redact_operator_intel_payload(obj: Any, *, depth: int = 0) -> Any:
    """Entfernt typische Secret-/Prompt-Pfade aus verschachtelten dict/list-Strukturen."""
    if depth > 12:
        return "[truncated_depth]"
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k).lower()
            if any(s in ks for s in _REDACT_KEY_SUBSTRINGS):
                out[k] = "[redacted]"
                continue
            out[k] = redact_operator_intel_payload(v, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [redact_operator_intel_payload(x, depth=depth + 1) for x in obj[:80]]
    if isinstance(obj, str) and len(obj) > 2000:
        return obj[:2000] + "…"
    return obj


def format_operator_intel_message(payload: dict[str, Any]) -> str:
    """
    Baut den Telegram-Text aus validiertem Intel-Payload.
    Erwartet u.a. intel_kind, symbol; optionale Kontextfelder.
    """
    p = redact_operator_intel_payload(dict(payload))
    kind = str(p.get("intel_kind") or "execution_update").strip().lower()
    label = _INTEL_KIND_TO_LABEL.get(kind, kind.upper())
    lines: list[str] = [f"[{label}]"]

    cid = p.get("correlation_id")
    if cid:
        lines.append(f"ref: {cid}")

    def _line(title: str, key: str) -> None:
        v = p.get(key)
        if v in (None, "", [], {}):
            return
        if isinstance(v, (list, tuple)):
            v = "; ".join(str(x) for x in v[:12])
        lines.append(f"{title}: {v}")

    _line("Instrument", "symbol")
    _line("Familie", "market_family")
    _line("Playbook", "playbook_id")
    _line("Route", "specialist_route")
    _line("Regime", "regime")
    _line("Risiko", "risk_summary")
    _line("Stop/Exit-Familie", "stop_exit_family")
    _line("Hebel-Band", "leverage_band")
    _line("Outcome", "outcome")
    _line("Execution", "execution_id")
    _line("Signal", "signal_id")
    _line("Order (lokal)", "internal_order_id")

    reasons = p.get("reasons")
    if isinstance(reasons, list) and reasons:
        rtxt = "; ".join(str(x) for x in reasons[:10])
        lines.append(f"Gruende: {rtxt}")
    elif isinstance(reasons, str) and reasons.strip():
        lines.append(f"Gruende: {reasons.strip()[:900]}")

    notes = p.get("notes")
    if isinstance(notes, str) and notes.strip():
        lines.append(f"Hinweis: {notes.strip()[:500]}")

    text = "\n".join(lines)
    # keine Markdown-Injection in plain mode
    text = re.sub(r"```", "` ` `", text)
    return text


def build_operator_intel_envelope_payload(
    *,
    intel_kind: str,
    symbol: str,
    correlation_id: str | None = None,
    market_family: str | None = None,
    playbook_id: str | None = None,
    specialist_route: str | None = None,
    regime: str | None = None,
    risk_summary: str | None = None,
    stop_exit_family: str | None = None,
    leverage_band: str | None = None,
    reasons: list[str] | str | None = None,
    outcome: str | None = None,
    execution_id: str | None = None,
    signal_id: str | None = None,
    internal_order_id: str | None = None,
    reply_to_telegram_message_id: int | None = None,
    severity: str = "info",
    dedupe_key: str | None = None,
    dedupe_ttl_minutes: int = 0,
    notes: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flacher Payload fuer event_type=operator_intel (vor redact nochmal durch Publisher)."""
    pl: dict[str, Any] = {
        "intel_kind": intel_kind,
        "symbol": symbol,
        "severity": severity,
        "intel_format_version": 1,
    }
    if correlation_id:
        pl["correlation_id"] = correlation_id
    if market_family:
        pl["market_family"] = market_family
    if playbook_id:
        pl["playbook_id"] = playbook_id
    if specialist_route:
        pl["specialist_route"] = specialist_route
    if regime:
        pl["regime"] = regime
    if risk_summary:
        pl["risk_summary"] = risk_summary
    if stop_exit_family:
        pl["stop_exit_family"] = stop_exit_family
    if leverage_band:
        pl["leverage_band"] = leverage_band
    if reasons is not None:
        pl["reasons"] = reasons
    if outcome:
        pl["outcome"] = outcome
    if execution_id:
        pl["execution_id"] = execution_id
    if signal_id:
        pl["signal_id"] = signal_id
    if internal_order_id:
        pl["internal_order_id"] = internal_order_id
    if reply_to_telegram_message_id is not None:
        pl["reply_to_telegram_message_id"] = int(reply_to_telegram_message_id)
    if dedupe_key:
        pl["dedupe_key"] = dedupe_key
    if dedupe_ttl_minutes:
        pl["dedupe_ttl_minutes"] = int(dedupe_ttl_minutes)
    if notes:
        pl["notes"] = notes
    if extra:
        pl["extra"] = redact_operator_intel_payload(extra)
    pl["text"] = format_operator_intel_message(pl)
    return redact_operator_intel_payload(pl)
