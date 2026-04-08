"""Stabile IDs und Fingerprints fuer Replay/Backtest (Prompt 27).

Die Namespaces sind fest und duerfen nicht geaendert werden, sonst aendern sich
alle abgeleiteten UUIDs.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

# Feste UUID5-Namespaces (nicht aendern)
_NAMESPACE_REPLAY_SESSION = uuid.UUID("766563b1-6f27-4c27-a9e0-5277d8c27b01")
_NAMESPACE_STREAM_EVENT = uuid.UUID("8891c2d3-4e38-5f4a-b1c2-d3e4f5a6b7c8")
_NAMESPACE_BACKTEST_RUN = uuid.UUID("9a02d3e4-5f49-4a5b-c2d3-e4f5a6b7c8d9")

REPLAY_DETERMINISM_PROTOCOL_VERSION = "p27-v1"
SIGNAL_ID_DETERMINISM_VERSION = "sig-p30-v1"
DECISION_TRACE_ID_VERSION = "dtr-p30-v1"

_NAMESPACE_SIGNAL_ROW = uuid.UUID("b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e")
_NAMESPACE_DECISION_TRACE = uuid.UUID("c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f")

# Relativer Vergleich nur fuer aggregierte Float-Metriken (Tests/Reports).
# Fachliche Entscheidungen (Gates, Aktionen) duerfen nicht von dieser Toleranz abhaengen.
FLOAT_METRICS_RTOL = 1e-9


def normalized_timeframes(timeframes: list[str]) -> list[str]:
    """Kanonische Sortierung fuer SQL-ANY und Fingerprints (Laenge, dann lexikographisch)."""
    uniq = sorted({str(t).strip() for t in timeframes if str(t).strip()})
    return sorted(uniq, key=lambda x: (len(x), x.lower()))


def stable_replay_session_id(
    *,
    symbol: str,
    timeframes: list[str],
    from_ts_ms: int,
    to_ts_ms: int,
    speed_factor: float,
    dedupe_prefix: str,
    publish_ticks: bool,
) -> uuid.UUID:
    tfs = normalized_timeframes(timeframes)
    payload = json.dumps(
        {
            "v": REPLAY_DETERMINISM_PROTOCOL_VERSION,
            "symbol": symbol.upper().strip(),
            "timeframes": tfs,
            "from_ts_ms": from_ts_ms,
            "to_ts_ms": to_ts_ms,
            "speed_factor": float(speed_factor),
            "dedupe_prefix": dedupe_prefix,
            "publish_ticks": bool(publish_ticks),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return uuid.uuid5(_NAMESPACE_REPLAY_SESSION, payload)


def stable_stream_event_id(*, stream: str, dedupe_key: str) -> str:
    """Deterministische event_id fuer Redis/Streams (als UUID-String)."""
    name = f"{stream}\0{dedupe_key}"
    return str(uuid.uuid5(_NAMESPACE_STREAM_EVENT, name))


def trace_implies_replay_determinism(trace: dict[str, Any] | None) -> bool:
    """True wenn Trace von learning_engine.replay stammt (Kerze/Session-Manifest)."""
    if not trace:
        return False
    if str(trace.get("source") or "").strip() == "learning_engine.replay":
        return True
    det = trace.get("determinism")
    if isinstance(det, dict) and det.get("replay_session_id"):
        return True
    if trace.get("session_id") and str(trace.get("source") or "").strip() == "learning_engine.replay":
        return True
    return False


def stable_signal_row_id(
    *,
    replay_session_id: str,
    upstream_event_id: str,
    symbol: str,
    timeframe: str,
    analysis_ts_ms: int,
    signal_output_schema_version: str,
) -> str:
    """Deterministische signal_id fuer Replay-Ketten (UUID-String)."""
    payload = json.dumps(
        {
            "v": SIGNAL_ID_DETERMINISM_VERSION,
            "replay_session_id": str(replay_session_id).strip(),
            "upstream_event_id": str(upstream_event_id).strip(),
            "symbol": str(symbol).upper().strip(),
            "timeframe": str(timeframe).strip(),
            "analysis_ts_ms": int(analysis_ts_ms),
            "signal_output_schema_version": str(signal_output_schema_version).strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_NAMESPACE_SIGNAL_ROW, payload))


def stable_decision_trace_id(*, signal_id: str, decision_policy_version: str) -> str:
    """Stabile ID fuer Hybrid-/Risk-Entscheidungsschicht (Vergleich Live vs Shadow)."""
    payload = json.dumps(
        {
            "v": DECISION_TRACE_ID_VERSION,
            "signal_id": str(signal_id).strip(),
            "decision_policy_version": str(decision_policy_version).strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_NAMESPACE_DECISION_TRACE, payload))


def stable_offline_backtest_run_id(
    *,
    symbol: str,
    timeframes: list[str],
    from_ts_ms: int,
    to_ts_ms: int,
    cv_method: str,
    k_folds: int,
    embargo_pct: float,
    random_seed: int,
) -> uuid.UUID:
    tfs = normalized_timeframes(timeframes)
    payload = json.dumps(
        {
            "v": REPLAY_DETERMINISM_PROTOCOL_VERSION,
            "symbol": symbol.upper().strip(),
            "timeframes": tfs,
            "from_ts_ms": from_ts_ms,
            "to_ts_ms": to_ts_ms,
            "cv_method": cv_method,
            "k_folds": k_folds,
            "embargo_pct": float(embargo_pct),
            "random_seed": int(random_seed),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return uuid.uuid5(_NAMESPACE_BACKTEST_RUN, payload)


def float_compare_metrics(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    rtol: float = FLOAT_METRICS_RTOL,
) -> bool:
    """Vergleich aggregierter Metrik-Dicts: Schluessel exakt, Floats mit relativem rtol.

    Ganzzahlen, Strings, Booleans und verschachtelte Strukturen muessen exakt uebereinstimmen;
    nur fuer ``float``-Werte gilt ``abs(x-y) <= rtol * max(1, abs(x), abs(y))``.
    Kein ``atol`` (bei Bedarf Werte vorher runden oder rtol erhoehen).
    """
    if set(a.keys()) != set(b.keys()):
        return False
    for k in sorted(a.keys()):
        x, y = a[k], b[k]
        if x == y:
            continue
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) <= rtol * max(1.0, abs(x), abs(y)):
                continue
            return False
        return False
    return True
