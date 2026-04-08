from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from drawing_engine.schema_validate import validate_drawing_record
from drawing_engine.storage.repo import (
    DrawingRepository,
    fingerprint_drawing,
    input_gates_from_drawing_provenance,
)


def persist_drawing_batch(
    repo: DrawingRepository,
    *,
    symbol: str,
    timeframe: str,
    records: list[dict[str, Any]],
    ts_ms: int,
    batch_input_provenance: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> list[str]:
    """
    Schreibt Revisionen; gibt parent_ids zurueck, die neu geschrieben wurden.
    """
    log = logger or logging.getLogger("drawing_engine.persist")
    if not records:
        log.debug("persist skip: leere drawing-liste symbol=%s tf=%s", symbol, timeframe)
        return []

    keep = {str(r["parent_id"]) for r in records}
    expired = repo.expire_active_not_in(symbol=symbol, timeframe=timeframe, keep_parent_ids=keep)
    if expired:
        log.debug("expired %s orphan active drawings for %s %s", expired, symbol, timeframe)

    input_gates = (
        input_gates_from_drawing_provenance(batch_input_provenance)
        if batch_input_provenance is not None
        else None
    )

    changed: list[str] = []
    for rec in records:
        pid = str(rec["parent_id"])
        fp = fingerprint_drawing(rec, input_gates=input_gates)
        prev = repo.latest_active_fingerprint(parent_id=pid)
        if prev == fp:
            continue
        repo.expire_active_parent(parent_id=pid)
        next_rev = repo.max_revision(parent_id=pid) + 1
        final = {
            **rec,
            "revision": next_rev,
            "drawing_id": str(uuid4()),
            "created_ts_ms": ts_ms,
            "updated_ts_ms": ts_ms,
            "status": "active",
        }
        validate_drawing_record(final)
        repo.insert_revision(
            drawing_id=final["drawing_id"],
            parent_id=pid,
            revision=next_rev,
            symbol=symbol,
            timeframe=timeframe,
            drawing_type=final["type"],
            geometry=final["geometry"],
            style=final["style"],
            reasons=list(final["reasons"]),
            confidence=float(final["confidence"]),
            ts_ms=ts_ms,
            input_provenance=batch_input_provenance or {},
        )
        changed.append(pid)
    return changed
