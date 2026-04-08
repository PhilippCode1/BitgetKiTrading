"""Persistenz fuer app.signal_explanations (Prompt 14)."""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg
from psycopg.rows import dict_row


class ExplanationRepository:
    def __init__(self, database_url: str, *, logger: logging.Logger | None = None) -> None:
        self._database_url = database_url
        self._logger = logger or logging.getLogger("signal_engine.explanations_repo")

    def upsert_for_signal(self, *, signal_id: str, bundle: dict[str, Any]) -> None:
        sql = """
        INSERT INTO app.signal_explanations (
            signal_id,
            explain_version,
            explain_short,
            explain_long_md,
            explain_long_json,
            risk_warnings_json,
            stop_explain_json,
            targets_explain_json
        ) VALUES (
            %s::uuid,
            %s,
            %s,
            %s,
            %s::jsonb,
            %s::jsonb,
            %s::jsonb,
            %s::jsonb
        )
        ON CONFLICT (signal_id) DO UPDATE SET
            explain_version = EXCLUDED.explain_version,
            explain_short = EXCLUDED.explain_short,
            explain_long_md = EXCLUDED.explain_long_md,
            explain_long_json = EXCLUDED.explain_long_json,
            risk_warnings_json = EXCLUDED.risk_warnings_json,
            stop_explain_json = EXCLUDED.stop_explain_json,
            targets_explain_json = EXCLUDED.targets_explain_json,
            updated_at = now()
        """
        params = (
            signal_id,
            bundle["explain_version"],
            bundle["explain_short"],
            bundle["explain_long_md"],
            json.dumps(bundle["explain_long_json"], separators=(",", ":"), ensure_ascii=False),
            json.dumps(bundle["risk_warnings_json"], separators=(",", ":"), ensure_ascii=False),
            json.dumps(bundle["stop_explain_json"], separators=(",", ":"), ensure_ascii=False),
            json.dumps(bundle["targets_explain_json"], separators=(",", ":"), ensure_ascii=False),
        )
        with self._connect() as conn:
            conn.execute(sql, params)

    def fetch_by_signal_id(self, signal_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT explain_version, explain_short, explain_long_md, explain_long_json,
               risk_warnings_json, stop_explain_json, targets_explain_json,
               created_at, updated_at
        FROM app.signal_explanations
        WHERE signal_id = %s::uuid
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (signal_id,)).fetchone()
        if row is None:
            return None
        return _parse_explanation_row(dict(row))

    def _connect(self, **kwargs: Any) -> psycopg.Connection[Any]:
        kw: dict[str, Any] = {"connect_timeout": 5, "autocommit": True}
        kw.update(kwargs)
        return psycopg.connect(self._database_url, **kw)


def _parse_explanation_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for k in (
        "explain_long_json",
        "risk_warnings_json",
        "stop_explain_json",
        "targets_explain_json",
    ):
        if k in out and isinstance(out[k], str):
            out[k] = json.loads(out[k])
    if out.get("created_at") is not None:
        out["created_at"] = out["created_at"].isoformat()
    if out.get("updated_at") is not None:
        out["updated_at"] = out["updated_at"].isoformat()
    return out
