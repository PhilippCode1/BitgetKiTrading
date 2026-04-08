from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Json

from news_engine.models import NewsCandidate

logger = logging.getLogger("news_engine.repo")


class NewsRepository:
    def __init__(self, database_url: str, *, logger_: logging.Logger | None = None) -> None:
        self._database_url = database_url
        self._logger = logger_ or logger

    def _connect(self, **kwargs: Any) -> psycopg.Connection[Any]:
        kw: dict[str, Any] = {"connect_timeout": 5, "autocommit": True}
        kw.update(kwargs)
        return psycopg.connect(self._database_url, **kw)

    def insert_candidate(
        self,
        candidate: NewsCandidate,
        *,
        ingested_ts_ms: int,
    ) -> tuple[int, str] | None:
        """INSERT mit Dedupe (url + source/source_item_id). Gibt (id, news_id) oder None."""
        news_id = uuid4()
        raw: dict[str, Any] = {
            "ingestion_version": "1",
            "source": candidate.source,
            "fragment": candidate.raw_fragment,
        }
        if candidate.ingest_channel:
            raw["ingest_channel"] = candidate.ingest_channel
        sql = """
        INSERT INTO app.news_items (
            news_id, source, source_item_id, title, description, content, url, author, language,
            raw_json, published_ts, published_ts_ms, ingested_ts_ms
        ) VALUES (
            %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            CASE WHEN %s IS NULL THEN NULL
                 ELSE to_timestamp(%s / 1000.0) END,
            %s, %s
        )
        ON CONFLICT (url) DO NOTHING
        RETURNING id, news_id::text
        """
        pub_ms = candidate.published_ts_ms
        params = (
            str(news_id),
            candidate.source,
            candidate.source_item_id,
            candidate.title,
            candidate.description,
            candidate.content,
            candidate.url,
            candidate.author,
            candidate.language,
            json.dumps(raw, separators=(",", ":"), ensure_ascii=False),
            pub_ms,
            pub_ms,
            pub_ms,
            ingested_ts_ms,
        )
        try:
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        except errors.UniqueViolation:
            self._logger.debug(
                "dedupe unique violation source=%s sid=%s",
                candidate.source,
                candidate.source_item_id,
            )
            return None
        if row is None:
            return None
        return int(row[0]), str(row[1])

    def list_latest(self, *, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT id, news_id::text AS news_id, source, source_item_id, title, description, url,
               author, language, published_ts, published_ts_ms, ingested_ts_ms,
               relevance_score, sentiment, impact_window, scored_ts_ms, scoring_version,
               created_ts
        FROM app.news_items
        ORDER BY COALESCE(published_ts_ms, (EXTRACT(EPOCH FROM published_ts) * 1000)::bigint) DESC NULLS LAST,
                 published_ts DESC NULLS LAST,
                 id DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("created_ts") is not None:
                d["created_ts"] = d["created_ts"].isoformat()
            if d.get("published_ts") is not None:
                d["published_ts"] = d["published_ts"].isoformat()
            if d.get("relevance_score") is not None:
                d["relevance_score"] = int(d["relevance_score"])
            out.append(d)
        return out

    def fetch_pending_scoring(self, *, scoring_version: str, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT id, news_id::text AS news_id, title, description, content, source, url,
               published_ts_ms, raw_json
        FROM app.news_items
        WHERE scored_ts_ms IS NULL
           OR scoring_version IS DISTINCT FROM %s
           OR scoring_version IS NULL
        ORDER BY COALESCE(published_ts_ms, 0) DESC, id ASC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (scoring_version, limit)).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            rj = d.get("raw_json")
            if isinstance(rj, str):
                try:
                    d["raw_json"] = json.loads(rj)
                except json.JSONDecodeError:
                    d["raw_json"] = {}
            elif rj is None:
                d["raw_json"] = {}
            out.append(d)
        return out

    def update_scoring_row(
        self,
        row_id: int,
        *,
        relevance_score: int,
        sentiment: str,
        impact_window: str,
        scored_ts_ms: int,
        scoring_version: str,
        llm_summary_json: dict[str, Any] | None,
        entities_json: list[Any] | None,
    ) -> None:
        sql = """
        UPDATE app.news_items SET
            relevance_score = %s,
            sentiment = %s,
            impact_window = %s,
            scored_ts_ms = %s,
            scoring_version = %s,
            llm_summary_json = COALESCE(%s, llm_summary_json),
            entities_json = COALESCE(%s, entities_json)
        WHERE id = %s
        """
        llm_j = Json(llm_summary_json) if llm_summary_json is not None else None
        ent_j = Json(entities_json) if entities_json is not None else None
        params = (
            relevance_score,
            sentiment,
            impact_window,
            scored_ts_ms,
            scoring_version,
            llm_j,
            ent_j,
            row_id,
        )
        with self._connect() as conn:
            conn.execute(sql, params)

    def list_scored(self, *, min_score: int, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT id, news_id::text AS news_id, source, title, description, url,
               published_ts_ms, relevance_score, sentiment, impact_window,
               scored_ts_ms, scoring_version
        FROM app.news_items
        WHERE relevance_score >= %s
        ORDER BY relevance_score DESC, published_ts_ms DESC NULLS LAST, id DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (min_score, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("relevance_score") is not None:
                d["relevance_score"] = int(d["relevance_score"])
            out.append(d)
        return out

    def get_by_id(self, row_id: int) -> dict[str, Any] | None:
        sql = """
        SELECT id, news_id::text AS news_id, source, source_item_id, title, description, content,
               url, author, language, published_ts, published_ts_ms, ingested_ts_ms,
               relevance_score, sentiment, impact_window, scored_ts_ms, scoring_version,
               llm_summary_json, entities_json, raw_json, created_ts
        FROM app.news_items
        WHERE id = %s
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (row_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        if d.get("published_ts") is not None:
            d["published_ts"] = d["published_ts"].isoformat()
        if d.get("relevance_score") is not None:
            d["relevance_score"] = int(d["relevance_score"])
        return d


def utc_now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
