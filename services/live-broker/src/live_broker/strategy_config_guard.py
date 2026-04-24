from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("live_broker.strategy_config_guard")


def verify_bound_strategy_version_or_raise(
    dsn: str, *, version_id: str, expected_hash: str
) -> None:
    """RuntimeError wenn gebundene strategy_versions.configuration_hash abweicht."""
    vid = UUID(version_id)
    h = (expected_hash or "").strip().lower()
    if not h:
        raise RuntimeError("LIVE_BROKER_STRATEGY_CONFIG_CHECKSUM leer (erforderlich)")

    q = "SELECT configuration_hash FROM learn.strategy_versions WHERE strategy_version_id = %s"
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        row = conn.execute(q, (str(vid),)).fetchone()
    if row is None:
        raise RuntimeError("strategy_version_id in learn.strategy_versions unbekannt")

    d = dict(row)
    ch = (str(d.get("configuration_hash") or "")).strip().lower()
    if ch != h:
        a, b = h[:12], (ch[:12] if ch else "missing")
        raise RuntimeError(f"STRATEGY_CONFIG_CHECKSUM mismatch: exp={a}.. db={b}..")


def should_verify(settings: Any) -> bool:
    p = (getattr(settings, "live_broker_strategy_version_id", "") or "").strip()
    hx = (getattr(settings, "live_broker_strategy_config_expected_hash", "") or "").strip()
    return bool(p and hx)
