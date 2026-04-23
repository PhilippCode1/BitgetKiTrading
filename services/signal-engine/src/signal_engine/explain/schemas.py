from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExplainInput:
    """Nur Fakten aus DB/Scoring — keine erfundenen Marktdaten."""

    signal_row: dict[str, Any]
    structure_state: dict[str, Any] | None
    structure_events: list[dict[str, Any]]
    primary_feature: dict[str, Any] | None
    features_by_tf: dict[str, dict[str, Any] | None]
    drawings: list[dict[str, Any]]
    news_row: dict[str, Any] | None
    last_close: float | None
    foundation_model_tsfm: dict[str, Any] | None = None
