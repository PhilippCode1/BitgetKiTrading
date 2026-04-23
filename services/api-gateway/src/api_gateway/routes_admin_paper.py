from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from api_gateway.audit import record_gateway_audit_line
from api_gateway.auth import GatewayAuthContext, require_admin_write_role
from api_gateway.db import get_database_url
from api_gateway.db_paper_mutations import (
    paper_account_admin_adjustment,
    paper_account_deposit_demo,
    paper_reset_demo_account,
    resolve_primary_paper_account_id,
)

router = APIRouter(prefix="/v1/admin/paper", tags=["admin-paper"])


def _parse_decimal(label: str, raw: str) -> Decimal:
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid {label}") from exc


class PaperDepositBody(BaseModel):
    amount_usdt: str = Field(
        ...,
        description="Positiv = Demo-Gutschrift, negativ = Demo-Abbuchung",
    )
    account_id: str | None = None
    note: str | None = None


class PaperAdjustBody(BaseModel):
    delta_usdt: str
    account_id: str | None = None
    note: str | None = None


class PaperResetBody(BaseModel):
    new_initial_equity_usdt: str
    account_id: str | None = None
    purge_trade_evaluations: bool = True
    note: str | None = Field(
        default=None,
        description="Grund fuer Audit / Operator-Notiz",
    )


def _resolve_account_id(conn: psycopg.Connection[Any], explicit: str | None) -> UUID:
    if explicit and explicit.strip():
        return UUID(explicit.strip())
    aid = resolve_primary_paper_account_id(conn)
    if aid is None:
        raise HTTPException(status_code=404, detail="no paper account")
    return aid


@router.post("/account/deposit-demo")
def admin_paper_deposit_demo(
    request: Request,
    body: PaperDepositBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_write_role)],
) -> dict[str, Any]:
    amt = _parse_decimal("amount_usdt", body.amount_usdt)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
        try:
            aid = _resolve_account_id(conn, body.account_id)
            out = paper_account_deposit_demo(
                conn,
                account_id=aid,
                amount_usdt=amt,
                note=body.note,
            )
            conn.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_gateway_audit_line(
        request,
        auth,
        "admin_paper_deposit_demo",
        extra={"account_id": out["account_id"], "amount": str(amt)},
    )
    return {"ok": True, **out}


@router.post("/account/adjust")
def admin_paper_adjust(
    request: Request,
    body: PaperAdjustBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_write_role)],
) -> dict[str, Any]:
    delta = _parse_decimal("delta_usdt", body.delta_usdt)
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8) as conn:
        try:
            aid = _resolve_account_id(conn, body.account_id)
            out = paper_account_admin_adjustment(
                conn,
                account_id=aid,
                delta_usdt=delta,
                note=body.note,
            )
            conn.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_gateway_audit_line(
        request,
        auth,
        "admin_paper_adjust",
        extra={"account_id": out["account_id"], "delta": str(delta)},
    )
    return {"ok": True, **out}


@router.post("/account/reset-demo")
def admin_paper_reset_demo(
    request: Request,
    body: PaperResetBody,
    auth: Annotated[GatewayAuthContext, Depends(require_admin_write_role)],
) -> dict[str, Any]:
    initial = _parse_decimal("new_initial_equity_usdt", body.new_initial_equity_usdt)
    if initial < 0:
        raise HTTPException(
            status_code=400,
            detail="new_initial_equity_usdt must be >= 0",
        )
    dsn = get_database_url()
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        try:
            aid = _resolve_account_id(conn, body.account_id)
            out = paper_reset_demo_account(
                conn,
                account_id=aid,
                new_initial_equity=initial,
                purge_trade_evaluations=body.purge_trade_evaluations,
                note=body.note,
            )
            conn.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_gateway_audit_line(
        request,
        auth,
        "admin_paper_reset_demo",
        extra={
            "account_id": out["account_id"],
            "positions_deleted": out["positions_deleted"],
            "purge_trade_evaluations": body.purge_trade_evaluations,
        },
    )
    return {"ok": True, **out}
