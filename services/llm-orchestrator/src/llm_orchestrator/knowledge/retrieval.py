from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from llm_orchestrator.knowledge.onchain_macro import build_readonly_onchain_text

logger = logging.getLogger("llm_orchestrator.knowledge")

# Hartes Timeout pro Block (Serialisierung/Fetch, Pro-Symbol-robust, max. 2s)
_CONTEXT_SECTION_TIMEOUT_SEC = 2.0
_CONTEXT_FETCH_LOG_PREFIX = "operator_readonly_context"

T = TypeVar("T")

# Explizite Platzhalter fuer fehlende/leere Marktdaten (BFF liefert Teil-JSON)
# News: fester Null-Data-String (Audit: Luecke sichtbar, kein Ersatzinventar)
PLACEHOLDER_NO_NEWS = "[KEINE AKTUELLEN NEWS VERFÜGBAR]"
PLACEHOLDER_NO_ORDERBOOK = "[KEIN AKTUELLES ORDERBUCH VERFÜGBAR]"
PLACEHOLDER_NO_SIGNALS = "[KEINE AKTUELLEN SIGNAL-DATEN VERFÜGBAR]"
PLACEHOLDER_NO_CHART = "[KEIN AKTUELLER CHART-/KERZENSNAPSHOT VERFÜGBAR]"
PLACEHOLDER_NO_ONCHAIN_MACRO = (
    "[KEINE ON-CHAIN-MAKRO-EVENTS VERFÜGBAR — Sniffer-Stream leer oder Redis nicht erreichbar]"
)
PLACEHOLDER_SECTION_ERROR = "[ABSCHNITT VORLAEUFIG NICHT LESBAR]"


def _run_with_timeout(
    fn: Callable[[], T], *, timeout_sec: float, on_timeout: T, label: str
) -> T:
    """Kurzes Timeout (Thread+Future), blockiert nicht bei pathologischen Werten."""
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            out = fut.result(timeout=timeout_sec)
        except Exception as exc:
            dt = time.perf_counter() - t0
            logger.warning(
                "%s: abschnitt=%s nach %.3fs: %s",
                _CONTEXT_FETCH_LOG_PREFIX,
                label,
                dt,
                type(exc).__name__,
            )
            return on_timeout
    return out


def _is_empty_value(v: Any) -> bool:
    if v is None:
        return True
    if v is False:
        return False
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, tuple, dict, set)) and len(v) == 0:
        return True
    return False


def _first_present(ctx: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in ctx and not _is_empty_value(ctx.get(k)):
            return ctx.get(k)
    return None


def _serialize_block(label: str, data: Any, empty_placeholder: str) -> str:
    """Pro Block isoliert: pathologische Werte -> Platzhalter, kein globaler Abbruch."""
    try:
        if _is_empty_value(data):
            return f"{label}:\n{empty_placeholder}"
        try:
            if isinstance(data, (dict, list)):
                text = json.dumps(data, ensure_ascii=False, default=str, indent=2)
            else:
                text = str(data)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "%s: serialisierung %s: %s", _CONTEXT_FETCH_LOG_PREFIX, label, exc
            )
            return f"{label}:\n{empty_placeholder}"
        if not (text or "").strip():
            return f"{label}:\n{empty_placeholder}"
        return f"{label}:\n{text.strip()}"
    except Exception as exc:
        logger.warning(
            "%s: abschnitt %s unerwartet: %s", _CONTEXT_FETCH_LOG_PREFIX, label, exc
        )
        return f"{label}:\n{empty_placeholder}"


def _section(
    label: str,
    data: Any,
    empty_ph: str,
    *,
    timeout_sec: float = _CONTEXT_SECTION_TIMEOUT_SEC,
    on_timeout: str | None = None,
) -> str:
    def _build() -> str:
        return _serialize_block(label, data, empty_ph)

    oto = on_timeout or f"{label}:\n{PLACEHOLDER_SECTION_ERROR}"
    return _run_with_timeout(
        _build,
        timeout_sec=timeout_sec,
        on_timeout=oto,
        label=label,
    )


def _isolated_data_section(
    label: str,
    data: Any,
    empty_ph: str,
    *,
    timeout_sec: float = _CONTEXT_SECTION_TIMEOUT_SEC,
) -> str:
    """
    Pro Abschnitt (News, Orderbook, …): try-except + 2s-Thread-Timeout,
    bei Fehlschlag exakt Null-Data-String (kein globaler Abbruch).
    """
    try:
        return _section(
            label,
            data,
            empty_ph,
            timeout_sec=timeout_sec,
            on_timeout=f"{label}:\n{empty_ph}",
        )
    except Exception as exc:
        logger.warning(
            "%s: isoliert data abschnitt=%s: %s", _CONTEXT_FETCH_LOG_PREFIX, label, exc
        )
        return f"{label}:\n{empty_ph}"


def _isolated_thread_block(
    label: str,
    fn: Callable[[], str],
    *,
    timeout_sec: float = _CONTEXT_SECTION_TIMEOUT_SEC,
    on_timeout: str,
) -> str:
    try:
        return _run_with_timeout(
            fn, timeout_sec=timeout_sec, on_timeout=on_timeout, label=label
        )
    except Exception as exc:
        logger.warning(
            "%s: isoliert thread label=%s: %s",
            _CONTEXT_FETCH_LOG_PREFIX,
            label,
            exc,
        )
        return on_timeout


def format_operator_readonly_pro_symbol(
    readonly_context: dict[str, Any] | None,
    *,
    max_total_chars: int = 10_000,
) -> str:
    """
    Baut den READONLY-Block fuer Operator-Explain: News, Orderbook, Signale, Chart
    in isolierten logischen Schritten; Serialisierung pro Block max. 2s (Timeout).
    Fehlende oder leere Quellen: explizite Platzhalter, kein Abbruch des LLM-Requests.
    """
    if not isinstance(readonly_context, dict):
        return (
            f"symbol:\n(ungueltiger Kontext — kein JSON-Objekt)\n\n"
            f"news:\n{PLACEHOLDER_NO_NEWS}\n\n"
            f"orderbook:\n{PLACEHOLDER_NO_ORDERBOOK}\n\n"
            f"signals:\n{PLACEHOLDER_NO_SIGNALS}\n\n"
            f"chart:\n{PLACEHOLDER_NO_CHART}\n\n"
            f"onchain_macro:\n{PLACEHOLDER_NO_ONCHAIN_MACRO}"
        )[:max_total_chars]

    ctx = readonly_context
    parts: list[str] = []

    # Symbol / Instrument (fuer Pro-Symbol-Bezug; kein harter Abbruch wenn fehlt)
    def _meta() -> str:
        lines: list[str] = []
        for key in ("symbol", "instrument", "pair", "product_id"):
            v = ctx.get(key)
            if v is not None and str(v).strip():
                lines.append(f"{key}={v!s}")
        if not lines:
            return (
                "symbol:\n("
                "nicht explizit gesetzt; trotzdem nutzen, fehlende Marktdaten benennen)"
            )
        return "symbol:\n" + "\n".join(lines)

    _symbol_timeout = (
        "symbol:\n(nicht explizit — fehlende Marktdaten im READONLY beachten)"
    )
    parts.append(
        _isolated_thread_block(
            "symbol",
            _meta,
            timeout_sec=_CONTEXT_SECTION_TIMEOUT_SEC,
            on_timeout=_symbol_timeout,
        )
    )

    news_d = _first_present(ctx, "news", "news_context", "headlines", "news_items")
    parts.append(
        _isolated_data_section("news", news_d, PLACEHOLDER_NO_NEWS),
    )
    ob_d = _first_present(
        ctx, "orderbook", "order_book", "book", "liquidity", "orderbook_snapshot"
    )
    parts.append(
        _isolated_data_section("orderbook", ob_d, PLACEHOLDER_NO_ORDERBOOK),
    )
    sig_d = _first_present(
        ctx, "signals", "signal", "signal_row", "signal_snapshot", "signal_context"
    )
    parts.append(
        _isolated_data_section("signals", sig_d, PLACEHOLDER_NO_SIGNALS),
    )
    ch_d = _first_present(
        ctx, "chart", "candles", "ohlc", "klines", "bars", "price_series"
    )
    parts.append(
        _isolated_data_section("chart", ch_d, PLACEHOLDER_NO_CHART),
    )

    def _onchain_macro_block() -> str:
        txt = build_readonly_onchain_text(ctx)
        if not (txt or "").strip():
            return f"onchain_macro:\n{PLACEHOLDER_NO_ONCHAIN_MACRO}"
        return f"onchain_macro:\n{txt.strip()}"

    parts.append(
        _isolated_thread_block(
            "onchain_macro",
            _onchain_macro_block,
            timeout_sec=_CONTEXT_SECTION_TIMEOUT_SEC,
            on_timeout=f"onchain_macro:\n{PLACEHOLDER_NO_ONCHAIN_MACRO}",
        )
    )

    # Weitere Schluessel (ohne Doppel) als zusaetzlicher Kontext, best-effort
    used = {
        "symbol",
        "instrument",
        "pair",
        "product_id",
        "news",
        "news_context",
        "headlines",
        "news_items",
        "orderbook",
        "order_book",
        "book",
        "liquidity",
        "orderbook_snapshot",
        "signals",
        "signal",
        "signal_row",
        "signal_snapshot",
        "signal_context",
        "chart",
        "candles",
        "ohlc",
        "klines",
        "bars",
        "price_series",
        "onchain",
        "onchain_macro",
        "onchain_context",
    }
    extra: dict[str, Any] = {k: v for k, v in ctx.items() if k not in used}
    if extra:

        def _extra() -> str:
            return _serialize_block("zusaetzlicher_kontext", extra, "")

        _zusatz_tmt = (
            "zusaetzlicher_kontext:\n[ZUSATZ Nicht serialisierbar in Zeitbudget]"
        )
        ex = _isolated_thread_block(
            "zusaetzlicher_kontext",
            _extra,
            timeout_sec=_CONTEXT_SECTION_TIMEOUT_SEC,
            on_timeout=_zusatz_tmt,
        )
        parts.append(ex)

    out = "\n\n".join(parts)
    if len(out) > max_total_chars:
        out = out[: max_total_chars] + "\n…"
    return out

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
    "ops_risk_assist": frozenset({"runbook", "playbook", "operator_explain"}),
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
