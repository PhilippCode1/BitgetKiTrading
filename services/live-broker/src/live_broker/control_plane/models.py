from __future__ import annotations

from pydantic import BaseModel, Field


class ControlPlaneReadHistoryRequest(BaseModel):
    """Nur Internal-Service-Auth; keine Roh-Exchange-Power nach aussen."""

    limit: int = Field(default=20, ge=1, le=100)
    symbol: str | None = None
    start_time_ms: str | None = None
    end_time_ms: str | None = None
    operator_jti: str | None = Field(
        default=None,
        description="Korrelation zu Operator-/Dashboard-Mutation (z. B. JWT jti oder UUID)",
    )
    audit_note: str | None = None


class ControlPlaneSetLeverageRequest(BaseModel):
    symbol: str
    leverage: str
    product_type: str | None = None
    margin_coin: str | None = None
    operator_jti: str | None = None
    source: str = "operator"
    reason: str = "control_plane_set_leverage"
    audit_note: str | None = None
