from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared_py.bitget.instruments import BitgetInstrumentIdentity


@dataclass
class ScoringContext:
    """Alle Eingaben fuer deterministisches Scoring (aus DB)."""

    symbol: str
    timeframe: str
    analysis_ts_ms: int
    structure_state: dict[str, Any] | None
    structure_events: list[dict[str, Any]]
    primary_feature: dict[str, Any] | None
    features_by_tf: dict[str, dict[str, Any] | None]
    drawings: list[dict[str, Any]]
    news_row: dict[str, Any] | None
    last_close: float | None
    instrument: BitgetInstrumentIdentity | None = None
    canonical_instrument_id: str | None = None
    previous_regime_snapshot: dict[str, Any] | None = None
    data_issues: list[str] = field(default_factory=list)
    instrument_execution_meta: dict[str, Any] | None = None


@dataclass
class LayerScore:
    score: float
    notes: list[str]
    flags: list[str] = field(default_factory=list)


@dataclass
class SignalBuildResult:
    signal_id: str
    payload_for_db: dict[str, Any]
    event_payload: dict[str, Any]
