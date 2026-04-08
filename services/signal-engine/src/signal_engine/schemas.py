"""API-Antwort-Modelle (ohne interne Fehlerdetails)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    service: str
    port: int


class SignalListResponse(BaseModel):
    status: str = "ok"
    symbol: str
    timeframe: str
    signals: list[dict[str, Any]]


class SignalSingleResponse(BaseModel):
    status: str = "ok"
    signal: dict[str, Any]


class SignalExplainResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    signal_id: str
    symbol: str | None = None
    timeframe: str | None = None
    explain_version: str
    explain_short: str
    explain_long_md: str
    explain_long_json: dict[str, Any]
    sections: dict[str, Any]
    risk_warnings: list[dict[str, Any]]
    stop_explain: dict[str, Any]
    targets_explain: dict[str, Any]


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str = Field(..., description="Sichere Nutzermeldung")
