"""
Gemeinsame Konstanten, Typ-Aliase und Pydantic-Vertraege fuer Signal Engine V1 (Event-Payload, API).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

# --- Klassische Typ-Aliase und Konstanten ---

SignalDirection = Literal["long", "short", "neutral"]
SignalClass = Literal["mikro", "kern", "gross", "warnung"]
DecisionState = Literal["accepted", "downgraded", "rejected"]
TradeAction = Literal["allow_trade", "do_not_trade"]
PlaybookDecisionMode = Literal["selected", "playbookless"]

# Meta-Entscheidung Prompt 22 — Lane unabhaengig vom binaeren trade_action (Execution).
MetaTradeLane = Literal[
    "do_not_trade", "shadow_only", "paper_only", "candidate_for_live"
]
META_TRADE_LANE_VALUES: tuple[str, ...] = (
    "do_not_trade",
    "shadow_only",
    "paper_only",
    "candidate_for_live",
)

# Finaler Meta-Entscheidungsaktionsraum (Kernel-Output, unabhaengig vom binaeren trade_action-Legacy).
MetaDecisionAction = Literal[
    "do_not_trade",
    "allow_trade_candidate",
    "candidate_for_live",
    "operator_release_pending",
    "blocked_by_policy",
]
META_DECISION_ACTION_VALUES: tuple[str, ...] = (
    "do_not_trade",
    "allow_trade_candidate",
    "candidate_for_live",
    "operator_release_pending",
    "blocked_by_policy",
)

# Trend aus Feature-Engine features.candle_features.trend_dir
TrendDirInt = Literal[-1, 0, 1]

SIGNAL_EVENT_SCHEMA_VERSION = "1.0"


# --- Neue hybride Bot-Trading-Vertraege (Pydantic V2) ---

class ExecutionMode(str, Enum):
    """
    Unterstuetzte Ausfuehrungsmodi fuer das hybride Trading-System.
    """
    BOT_GRID = "BOT_GRID"
    BOT_DCA = "BOT_DCA"
    STANDARD_FUTURES = "STANDARD_FUTURES"


class BotParams(BaseModel):
    """
    Konfigurationsparameter fuer Gitter- und DCA-Bots auf Bitget.
    """
    upper_bound: float = Field(
        gt=0,
        description="Obere Preisgrenze des Gitter-/DCA-Kanals"
    )
    lower_bound: float = Field(
        gt=0,
        description="Untere Preisgrenze des Gitter-/DCA-Kanals"
    )
    grid_count: int = Field(
        ge=2,
        le=500,
        description="Anzahl der Gitterlinien (Intervalle)"
    )
    trailing_enabled: bool = Field(
        description="Flag zur Aktivierung des dynamischen Preis-Trailings"
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> BotParams:
        """
        Verifiziert, dass die obere Grenze strikt ueber der unteren Grenze liegt.
        """
        if self.upper_bound <= self.lower_bound:
            raise ValueError("upper_bound muss strikt groesser als lower_bound sein")
        return self


class PayloadSignalCreated(BaseModel):
    """
    Pydantic-Datenvertrag fuer die 'signal_created' Event-Payload im hybriden Bot-System.
    """
    signal_id: str = Field(
        min_length=1,
        description="Eindeutiger Bezeichner des generierten Handelssignals"
    )
    direction: str = Field(
        description="Signalrichtung (z.B. 'long', 'short', 'neutral')"
    )
    market_regime: str | None = Field(
        default=None,
        description="Aktuelles Marktregime"
    )
    regime_bias: str | None = Field(
        default=None,
        description="Bias des Marktregimes"
    )
    regime_confidence_0_1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Regime-Konfidenz (normiert auf [0, 1])"
    )
    signal_strength_0_100: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Signalstaerke (normiert auf [0, 100])"
    )
    probability_0_1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Sicherungswahrscheinlichkeit der Prognose (normiert auf [0, 1])"
    )
    execution_mode: ExecutionMode = Field(
        description="Ausfuehrungsmodus des Trades (Bot vs. Direktional)"
    )
    bot_params: BotParams | None = Field(
        default=None,
        description="Zusatzparameter fuer Bot-Ausfuehrungsmodi (BOT_GRID, BOT_DCA)"
    )
    leverage_cap_applied: bool = Field(
        default=False,
        description="Indikator, ob die Risiko-Engine den Hebel limitiert hat"
    )

    model_config = ConfigDict(
        extra="allow",
        frozen=True
    )

    @model_validator(mode="after")
    def validate_bot_parameters(self) -> PayloadSignalCreated:
        """
        Stellt sicher, dass fuer Bot-Modi (BOT_GRID, BOT_DCA) die bot_params zwingend gesetzt sind.
        """
        if self.execution_mode in (ExecutionMode.BOT_GRID, ExecutionMode.BOT_DCA):
            if self.bot_params is None:
                raise ValueError(
                    f"Fuer den Modus {self.execution_mode.value} muessen 'bot_params' definiert sein"
                )
        return self
