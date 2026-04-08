from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("llm_orchestrator.knowledge")

# Task -> erlaubte Manifest-Tags (kuratiert, keine freie Websuche)
TASK_TAG_ALLOWLIST: dict[str, frozenset[str]] = {
    "news_summary": frozenset({"benchmark", "instrument", "playbook", "runbook"}),
    "analyst_hypotheses": frozenset({"playbook", "benchmark", "instrument"}),
    "analyst_context_classification": frozenset(
        {"playbook", "benchmark", "instrument", "runbook"}
    ),
    "post_trade_review": frozenset({"runbook", "playbook"}),
    "operator_explain": frozenset({"runbook", "playbook", "operator_explain"}),
    "safety_incident_diagnosis": frozenset(
        {"runbook", "playbook", "operator_explain"}
    ),
    "strategy_signal_explain": frozenset({"playbook", "instrument", "runbook"}),
    "ai_strategy_proposal_draft": frozenset({"playbook", "instrument", "runbook"}),
    "strategy_journal_summary": frozenset({"playbook", "instrument", "journal"}),
    "admin_operations_assist": frozenset({"runbook", "playbook", "operator_explain"}),
    "strategy_signal_assist": frozenset({"playbook", "instrument", "runbook"}),
    "customer_onboarding_assist": frozenset(
        {"playbook", "benchmark", "runbook", "operator_explain"}
    ),
    "support_billing_assist": frozenset({"runbook", "playbook", "operator_explain"}),
}


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    excerpt: str
    content_sha256: str


def _tokenize_query(q: str) -> set[str]:
    return {t for t in re.split(r"[^\w\-]+", q.lower()) if len(t) >= 3}


class KnowledgeRetriever:
    def __init__(
        self,
        *,
        knowledge_dir: Path,
        max_chunks: int,
        max_excerpt_chars: int,
    ) -> None:
        self._dir = knowledge_dir
        self._max_chunks = max(0, max_chunks)
        self._max_excerpt = max(64, max_excerpt_chars)
        self._manifest: dict[str, Any] = {}
        self._chunks_meta: list[dict[str, Any]] = []
        self._load_manifest()

    def _load_manifest(self) -> None:
        man_path = self._dir / "manifest.json"
        if not man_path.is_file():
            logger.warning("llm_knowledge manifest fehlt: %s", man_path)
            return
        try:
            self._manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("manifest nicht lesbar: %s", exc)
            return
        raw = self._manifest.get("chunks")
        if isinstance(raw, list):
            self._chunks_meta = [c for c in raw if isinstance(c, dict)]

    def retrieve(self, task_type: str, query_text: str) -> list[RetrievedChunk]:
        if self._max_chunks == 0 or not self._chunks_meta:
            return []
        allowed = TASK_TAG_ALLOWLIST.get(task_type)
        if not allowed:
            return []
        tokens = _tokenize_query(query_text)
        scored: list[tuple[int, dict[str, Any]]] = []
        for ch in self._chunks_meta:
            tags = ch.get("tags") or []
            if not isinstance(tags, list) or not tags:
                continue
            tag_set = {str(t).strip().lower() for t in tags if str(t).strip()}
            if not (tag_set & allowed):
                continue
            score = 0
            kw = ch.get("keywords") or []
            kw_list = kw if isinstance(kw, list) else []
            for k in kw_list:
                ks = str(k).lower()
                if ks and ks in query_text.lower():
                    score += 2
            cid = str(ch.get("id") or "")
            for t in tokens:
                if t in cid.replace("-", "_"):
                    score += 1
                for k in kw_list:
                    if t in str(k).lower():
                        score += 1
            scored.append((score, ch))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
        out: list[RetrievedChunk] = []
        base = self._dir.resolve()
        for _, ch in scored[: self._max_chunks * 3]:
            rel = str(ch.get("path") or "")
            if not rel or ".." in rel.replace("\\", "/"):
                continue
            target = (base / rel).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                logger.warning("chunk path ausserhalb knowledge_dir: %s", rel)
                continue
            if not target.is_file():
                continue
            try:
                raw_text = target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            excerpt = raw_text.strip()
            if len(excerpt) > self._max_excerpt:
                excerpt = excerpt[: self._max_excerpt] + "\n…"
            digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            rid = str(ch.get("id") or rel)
            out.append(RetrievedChunk(id=rid, excerpt=excerpt, content_sha256=digest))
            if len(out) >= self._max_chunks:
                break
        return out

    def format_for_prompt(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "(keine Retrieval-Ausschnitte)"
        parts: list[str] = []
        for c in chunks:
            parts.append(f"--- chunk_id={c.id} sha256={c.content_sha256} ---\n{c.excerpt}")
        return "\n\n".join(parts)
