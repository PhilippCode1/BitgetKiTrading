from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from audit_ledger.config import AuditLedgerSettings
from audit_ledger.ledger_repository import CommitResult, LedgerRepository
from config.bootstrap import bootstrap_from_settings
from shared_py.regulatory_audit_report_pdf import build_regulatory_audit_ledger_pdf_bytes, utc_now_iso
from shared_py.service_auth import (
    InternalServiceAuthContext,
    build_internal_service_dependency,
)

logger = logging.getLogger("audit_ledger.app")


class CommitWarRoomBody(BaseModel):
    market_event_json: dict[str, Any]
    war_room: dict[str, Any] = Field(
        ...,
        description="Vollstaendiges JSON-Ergebnis von ConsensusOrchestrator.evaluate().",
    )


class RegulatoryExportBody(BaseModel):
    period_from_iso: str | None = Field(default=None, description="ISO-8601 inclusive")
    period_to_iso: str | None = Field(default=None, description="ISO-8601 inclusive")


def build_app() -> FastAPI:
    settings = AuditLedgerSettings()
    bootstrap_from_settings("audit-ledger", settings)
    repo = LedgerRepository(settings)
    require_internal = build_internal_service_dependency(settings)

    app = FastAPI(title="audit-ledger", version="0.1.0")

    @app.get("/ready")
    def ready() -> PlainTextResponse:
        try:
            with psycopg.connect(repo._dsn) as conn:
                conn.execute("SELECT 1")
        except Exception as exc:  # pragma: no cover
            logger.warning("ready DB check failed: %s", exc)
            raise HTTPException(status_code=503, detail="database_unavailable") from exc
        return PlainTextResponse("ok", status_code=200)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "audit-ledger"}

    @app.post("/internal/v1/commit-war-room")
    def commit_war_room(
        body: CommitWarRoomBody,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        try:
            out: CommitResult = repo.commit_war_room(
                market_event_json=body.market_event_json,
                war_room=body.war_room,
            )
        except Exception as exc:
            logger.exception("commit_war_room failed")
            raise HTTPException(
                status_code=500,
                detail={"code": "AUDIT_LEDGER_COMMIT_FAILED", "message": str(exc)[:800]},
            ) from exc
        return {
            "ok": True,
            "apex_audit_ledger": {
                "decision_id": out.decision_id,
                "chain_hash_hex": out.chain_hash_hex,
                "prev_chain_hash_hex": out.prev_chain_hash_hex,
                "signature_hex": out.signature_hex,
                "signing_public_key_hex": out.public_key_hex,
            },
        }

    @app.get("/internal/v1/verify-chain")
    def verify_chain(
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> dict[str, Any]:
        ok, errors, n = repo.verify_full_chain()
        return {
            "chain_valid": ok,
            "entries_checked": n,
            "errors": errors,
        }

    @app.post("/internal/v1/regulatory-report.pdf")
    def regulatory_report_pdf(
        body: RegulatoryExportBody,
        _auth: InternalServiceAuthContext = Depends(require_internal),
    ) -> Response:
        rows = repo.list_entries_for_export(
            from_iso=body.period_from_iso,
            to_iso=body.period_to_iso,
        )
        for r in rows:
            if r.get("created_at") is not None:
                r["created_at"] = str(r["created_at"])
        pdf = build_regulatory_audit_ledger_pdf_bytes(
            title="Apex Predator Audit Ledger — Regulatory Hash Report",
            period_from_iso=body.period_from_iso or "—",
            period_to_iso=body.period_to_iso or "—",
            entries=rows,
            generated_at_iso=utc_now_iso(),
            footer_note=(
                "Hash-Kette: SHA256(prev_chain_hash || canonical_payload_utf8); "
                "Signatur: Ed25519 ueber chain_hash. Append-only-Tabelle in PostgreSQL."
            ),
        )
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="apex_audit_ledger_report.pdf"'
            },
        )

    return app
