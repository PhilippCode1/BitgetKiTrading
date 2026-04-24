from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from redis import Redis
from shared_py.eventbus import RedisStreamBus
from shared_py.observability.request_context import get_current_trace_ids

from llm_orchestrator.assist.context_policy import (
    filter_context_for_role,
    task_type_for_role,
)
from llm_orchestrator.assist.conversation_store import AssistConversationStore
from llm_orchestrator.cache.redis_cache import (
    LLMRedisCache,
    cache_key,
    stable_json_hash,
)
from llm_orchestrator.chart_annotation_sanitize import (
    sanitize_strategy_chart_annotations,
)
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.constants import LLM_ORCHESTRATOR_API_CONTRACT_VERSION
from llm_orchestrator.events.llm_failed import publish_llm_failed
from llm_orchestrator.exceptions import (
    GuardrailViolation,
    LLMPromptTooLargeError,
    RetryableLLMError,
)
from llm_orchestrator.guardrails import validate_task_output
from llm_orchestrator.knowledge.onchain_macro import (
    fetch_onchain_macro_context,
    merge_fetched_onchain_into_context,
)
from llm_orchestrator.knowledge.retrieval import (
    KnowledgeRetriever,
    RetrievedChunk,
    format_operator_readonly_pro_symbol,
)
from llm_orchestrator.llm_metrics import (
    record_llm_error,
    record_parsing_error,
    record_structured_run_outcome,
)
from llm_orchestrator.llm_request_metrics_context import (
    extract_tenant_id_from_object,
    set_llm_request_metrics,
)
from llm_orchestrator.paths import (
    llm_knowledge_dir,
    load_json_schema,
    news_summary_schema_path,
    prompts_dir,
)
from llm_orchestrator.prompt_governance import (
    build_ai_strategy_proposal_draft_user_prompt,
    build_operator_explain_user_prompt,
    build_safety_incident_diagnosis_user_prompt,
    build_strategy_signal_explain_user_prompt,
    load_prompt_manifest,
)
from llm_orchestrator.prompt_governance.templates import (
    build_assistant_turn_user_prompt,
)
from llm_orchestrator.quality_feedback_trace import (
    persist_operator_explain_row,
    persist_strategy_signal_explain_row,
)
from llm_orchestrator.providers.fake_provider import FakeProvider
from llm_orchestrator.providers.openai_provider import OpenAIProvider
from llm_orchestrator.retry.backoff import openai_circuit_trip_on_status, sleep_backoff
from llm_orchestrator.retry.circuit import CircuitBreaker
from llm_orchestrator.validation.schema_validate import (
    SchemaValidationError,
    compact_schema_for_repair_prompt,
    format_schema_errors_for_prompt,
    validate_against_schema,
)
from llm_orchestrator.validation.structured_fallback import (
    build_graceful_degradation_result,
    build_structured_fallback,
)
from llm_orchestrator.validation.structured_repair import (
    REPAIR_SYSTEM_APPEND_DE,
    build_repair_user_prompt,
)

logger = logging.getLogger("llm_orchestrator.service")

ProviderPref = Literal["auto", "openai"]

# Schnelle Klassifikations-/News-Tasks: hartes niedrigeres Timeout (siehe config)
_LLM_FAST_TIMEOUT_TASKS = frozenset(
    {
        "news_summary",
        "analyst_hypotheses",
        "analyst_context_classification",
    }
)

_MSG_DEGRADE_CIRCUIT_DE = (
    "Der KI-Provider steht wegen aufeinanderfolgender Fehler voruebergehend "
    "nicht zur Verfuegung (Fail-Closed; Sicherheitskreis / Circuit offen)."
)
_MSG_DEGRADE_TIMEOUT_DE = (
    "Die Bearbeitung hat die vorgesehene Wartezeit ueberschritten. "
    "Es wurde eine gueltige Mindeststruktur ohne vollstaendigen KI-Output geliefert."
)
_MSG_DEGRADE_UPSTREAM_DE = (
    "Der KI-Provider konnte die Anfrage nicht abschliessen. "
    "Es wurde eine gueltige Mindeststruktur ohne vollstaendigen KI-Output geliefert."
)
_MSG_DEGRADE_NO_PROVIDER_DE = (
    "Kein LLM-Provider ist konfiguriert. "
    "Es wurde eine gueltige Mindeststruktur (Fail-Closed) erzeugt."
)


def _classify_structured_failure(last_error: str) -> str:
    le = (last_error or "").strip()
    if not le:
        return "unknown"
    if le.startswith("circuit_open:"):
        return "circuit_open"
    if le.startswith("validation:"):
        return "schema_validation_exhausted"
    if "Kein LLM-Provider" in le or "Keys fehlen" in le:
        return "no_provider_configured"
    if "upstream timeout" in le.lower() or "rate limited" in le.lower():
        return "retry_exhausted"
    return "provider_failed"


class LLMService:
    def __init__(self, settings: LLMOrchestratorSettings) -> None:
        self._settings = settings
        self._failure_lock = threading.Lock()
        self._last_structured_failure: dict[str, Any] | None = None
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._cache = LLMRedisCache(self._redis, ttl_sec=settings.llm_cache_ttl_sec)
        self._bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
        )
        self._circuit = CircuitBreaker(
            fail_threshold=settings.llm_circuit_fail_threshold,
            open_seconds=settings.llm_circuit_open_sec,
            window_seconds=settings.llm_circuit_window_sec,
        )
        self._fake = FakeProvider()
        self._openai = OpenAIProvider(settings=settings)
        self._news_schema: dict[str, Any] = json.loads(
            news_summary_schema_path().read_text(encoding="utf-8")
        )
        self._schema_hypotheses = load_json_schema("analyst_hypotheses.schema.json")
        self._schema_context_cls = load_json_schema(
            "analyst_context_classification.schema.json"
        )
        self._schema_post_trade = load_json_schema("post_trade_review.schema.json")
        self._schema_operator_explain = load_json_schema("operator_explain.schema.json")
        self._schema_safety_incident_diagnosis = load_json_schema(
            "safety_incident_diagnosis.schema.json"
        )
        self._schema_strategy_signal_explain = load_json_schema(
            "strategy_signal_explain.schema.json"
        )
        self._schema_ai_strategy_proposal_draft = load_json_schema(
            "ai_strategy_proposal_draft.schema.json"
        )
        self._schema_journal = load_json_schema("strategy_journal_summary.schema.json")
        self._schema_assistant_turn_base = load_json_schema("assistant_turn.schema.json")
        self._assist_conv = AssistConversationStore(
            self._redis,
            ttl_sec=settings.llm_assist_conversation_ttl_sec,
            max_messages=settings.llm_assist_max_history_messages,
        )
        self._retriever = KnowledgeRetriever(
            knowledge_dir=llm_knowledge_dir(),
            max_chunks=settings.llm_knowledge_max_chunks,
            max_excerpt_chars=settings.llm_knowledge_excerpt_chars,
        )

    def _record_last_structured_failure(
        self,
        *,
        failure_class: str,
        message: str,
        task_type: str | None,
    ) -> None:
        msg = (message or "")[:800]
        with self._failure_lock:
            self._last_structured_failure = {
                "failure_class": failure_class,
                "message_snippet": msg,
                "task_type": task_type,
                "recorded_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }

    def peek_last_structured_failure(self) -> dict[str, Any] | None:
        with self._failure_lock:
            if self._last_structured_failure is None:
                return None
            return dict(self._last_structured_failure)

    def health(self) -> dict[str, Any]:
        redis_ok = False
        redis_error_class: str | None = None
        try:
            redis_ok = bool(self._redis.ping())
        except Exception as exc:
            redis_error_class = type(exc).__name__
        oa = self._openai.available
        fake = bool(self._settings.llm_use_fake_provider)
        any_provider = fake or oa
        provider_gap = not fake and not oa
        if fake:
            provider_mode = "fake"
        elif oa:
            provider_mode = "openai"
        else:
            provider_mode = "openai_key_missing"
        status = "ok" if redis_ok else "degraded"
        if provider_gap:
            status = "degraded"
        return {
            "status": status,
            "api_contract_version": LLM_ORCHESTRATOR_API_CONTRACT_VERSION,
            "app_env": self._settings.app_env,
            "production": bool(self._settings.production),
            "provider_mode": provider_mode,
            "provider_separation_note_de": (
                "Fake-Provider nur mit LLM_USE_FAKE_PROVIDER=true und APP_ENV nicht "
                "shadow/production. Produktive Antworten nutzen OpenAI structured outputs; "
                "Fake-Antworten sind mit [TEST-PROVIDER] gekennzeichnet."
            ),
            "structured_output": {
                "llm_timeout_ms": self._settings.llm_timeout_ms,
                "llm_request_timeout_ms_fast": self._settings.llm_request_timeout_ms_fast,
                "llm_request_timeout_ms_deep": self._settings.llm_request_timeout_ms_deep,
                "llm_max_retries": self._settings.llm_max_retries,
                "llm_max_prompt_chars": self._settings.llm_max_prompt_chars,
            },
            "backoff_sleep_determinism": (
                "LLM_BACKOFF_JITTER_RATIO=0: exponentielles Backoff ohne Zufall; "
                ">0: fester Zusatz exp*jitter_ratio*0.5 (kein RNG, siehe retry/backoff.py)."
            ),
            "redis_ok": redis_ok,
            "redis": {
                "ok": redis_ok,
                "last_error_class": redis_error_class,
            },
            "circuit": self._circuit.state_snapshot(),
            "fake_mode": fake,
            "openai_configured": oa,
            "any_provider_configured": any_provider,
            "llm_provider_gap": provider_gap,
            "last_structured_failure": self.peek_last_structured_failure(),
            "request_correlation": {
                "propagate_headers": ["X-Request-ID", "X-Correlation-ID"],
                "note": "Gateway/BFF leiten IDs weiter; Logs nutzen Contextvars im Orchestrator.",
            },
            "openai": {
                "structured_transport": self._openai.structured_transport_hint(),
                "sdk_has_responses": self._openai.sdk_has_responses,
                "use_responses_api": self._settings.llm_openai_use_responses_api,
                "allow_chat_fallback": self._settings.llm_openai_allow_chat_fallback,
                "models": {
                    "OPENAI_MODEL_PRIMARY": self._settings.openai_model_primary,
                    "OPENAI_MODEL_HIGH_REASONING": self._settings.openai_model_high_reasoning,
                    "OPENAI_MODEL_FAST": self._settings.openai_model_fast,
                },
            },
        }

    def _resolve_model_for_task(self, task_type: str | None) -> str:
        fast_tasks = frozenset({"news_summary"})
        high_tasks = frozenset(
            {
                "operator_explain",
                "safety_incident_diagnosis",
                "strategy_signal_explain",
                "ai_strategy_proposal_draft",
                "post_trade_review",
                "strategy_journal_summary",
                "admin_operations_assist",
                "strategy_signal_assist",
                "customer_onboarding_assist",
                "support_billing_assist",
                "ops_risk_assist",
            }
        )
        if not task_type:
            return self._settings.openai_model_primary
        if task_type in fast_tasks:
            return self._settings.openai_model_fast
        if task_type in high_tasks:
            return self._settings.openai_model_high_reasoning
        return self._settings.openai_model_primary

    def _llm_request_timeout_ms(self, task_type: str | None) -> int:
        t = (task_type or "").strip()
        if t in _LLM_FAST_TIMEOUT_TASKS:
            return min(
                self._settings.llm_request_timeout_ms_fast,
                self._settings.llm_timeout_ms,
            )
        return min(
            self._settings.llm_request_timeout_ms_deep,
            self._settings.llm_timeout_ms,
        )

    def _chain(
        self, preference: ProviderPref, resolved_openai_model: str
    ) -> list[tuple[Any, str]]:
        if self._settings.llm_use_fake_provider:
            return [(self._fake, self._fake.default_model)]
        o = (self._openai, resolved_openai_model) if self._openai.available else None
        if preference == "openai":
            lst = [x for x in [o] if x is not None]
        else:
            lst = [x for x in [o] if x is not None]
        if not lst:
            raise RuntimeError(
                "Kein LLM-Provider: Keys fehlen und LLM_USE_FAKE_PROVIDER=false"
            )
        return lst

    def _prompt_fingerprint(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def _governance_provenance(self, task_type: str | None) -> dict[str, Any]:
        m = load_prompt_manifest()
        meta: dict[str, Any] = {
            "prompt_manifest_version": m.manifest_version,
            "guardrails_version": m.guardrails_version,
        }
        if m.global_system_prompt_version:
            meta["global_system_prompt_version"] = m.global_system_prompt_version
        if task_type and (spec := m.task(task_type)):
            meta["prompt_task_version"] = spec.prompt_version
            meta["prompt_task_status"] = spec.status
        return meta

    def _build_provenance(
        self,
        *,
        schema_json: dict[str, Any],
        prompt: str,
        task_type: str | None,
        retrieval_chunks: list[RetrievedChunk] | None,
    ) -> dict[str, Any]:
        schema_id = str(schema_json.get("$id") or "")
        full_fp = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        prov: dict[str, Any] = {
            "task_type": task_type or "structured_adhoc",
            "llm_derived": True,
            "quantitative_core_note_de": (
                "Signale, Risk-Gates, Spezialisten-Stack, Broker und Orderpfad sind deterministische/harte "
                "Logik ausserhalb dieses Dienstes. Alle Felder unter result sind modellbasierte "
                "Schaetzungen oder Erklaerungen gemaess JSON-Schema und werden mit jsonschema validiert."
            ),
            "schema_id": schema_id,
            "prompt_fingerprint_sha256": full_fp,
            "retrieval": None,
            **self._governance_provenance(task_type),
        }
        if retrieval_chunks:
            prov["retrieval"] = {
                "source": "docs/llm_knowledge",
                "chunks": [
                    {"id": c.id, "content_sha256": c.content_sha256}
                    for c in retrieval_chunks
                ],
            }
        return prov

    def _finalize_response(
        self,
        base: dict[str, Any],
        *,
        schema_json: dict[str, Any],
        prompt: str,
        task_type: str | None,
        retrieval_chunks: list[RetrievedChunk] | None,
        provenance_extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        out = dict(base)
        prov = self._build_provenance(
            schema_json=schema_json,
            prompt=prompt,
            task_type=task_type,
            retrieval_chunks=retrieval_chunks,
        )
        if provenance_extras:
            prov = {**prov, **provenance_extras}
        out["provenance"] = prov
        return out

    def _backoff_duration_sec(self, attempt: int) -> float:
        exp = min(
            self._settings.llm_backoff_max_sec,
            self._settings.llm_backoff_base_sec * (2**attempt),
        )
        return exp + exp * self._settings.llm_backoff_jitter_ratio * 0.5

    def _graceful_degradation_out(
        self,
        *,
        schema_json: dict[str, Any],
        prompt: str,
        task_type: str | None,
        retrieval_chunks: list[RetrievedChunk] | None,
        use_model: str,
        failure_class: str,
        last_error: str,
        llm_error_code: str,
        public_message_de: str,
        schema_hash: str,
        input_hash: str,
        providers_tried: list[str],
        structured_fallback_binds: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result_obj = build_graceful_degradation_result(
            schema_json,
            task_type=task_type,
            public_message_de=public_message_de,
            fallback_binds=structured_fallback_binds,
        )
        try:
            publish_llm_failed(
                self._bus,
                schema_hash=schema_hash,
                input_hash=input_hash,
                error=last_error or "graceful_degradation",
                providers_tried=providers_tried,
            )
        except Exception as exc:
            logger.warning("llm_failed Event nicht publiziert: %s", exc)
        self._record_last_structured_failure(
            failure_class=failure_class,
            message=last_error or "graceful_degradation",
            task_type=task_type,
        )
        record_structured_run_outcome(task_type, "failure")
        prov_last = providers_tried[-1] if providers_tried else "none"
        record_llm_error(failure_class, prov_last)
        return self._finalize_response(
            {
                "ok": True,
                "orchestrator_status": "degraded",
                "llm_error_code": llm_error_code,
                "cached": False,
                "provider": "degraded",
                "model": use_model,
                "result": result_obj,
            },
            schema_json=schema_json,
            prompt=prompt,
            task_type=task_type,
            retrieval_chunks=retrieval_chunks,
            provenance_extras={
                "llm_derived": False,
                "graceful_degradation": True,
            },
        )

    def governance_summary(self) -> dict[str, Any]:
        m = load_prompt_manifest()
        baseline = prompts_dir() / "eval_baseline.json"
        bh16 = ""
        eval_cases_out: list[dict[str, Any]] = []
        eval_baseline_id = ""
        eval_release_gate = False
        if baseline.is_file():
            bh16 = hashlib.sha256(baseline.read_bytes()).hexdigest()[:16]
            try:
                bj = json.loads(baseline.read_text(encoding="utf-8"))
                eval_baseline_id = str(bj.get("baseline_id") or "")
                eval_release_gate = bool(bj.get("release_gate"))
                raw_cases = bj.get("cases")
                if isinstance(raw_cases, list):
                    for c in raw_cases:
                        if not isinstance(c, dict):
                            continue
                        cid = str(c.get("id") or "").strip()
                        if not cid:
                            continue
                        tt = c.get("task_types")
                        task_types = tt if isinstance(tt, list) else []
                        eval_cases_out.append(
                            {
                                "id": cid,
                                "description_de": str(c.get("description_de") or ""),
                                "category": str(c.get("category") or ""),
                                "task_types": [str(x) for x in task_types],
                            }
                        )
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        h = self.health()
        tasks_out: list[dict[str, Any]] = []
        for tid, spec in sorted(m.tasks.items()):
            tasks_out.append(
                {
                    "task_id": tid,
                    "prompt_version": spec.prompt_version,
                    "status": spec.status,
                    "guardrail_tier": spec.guardrail_tier,
                    "schema_filename": spec.schema_filename,
                }
            )
        return {
            "ok": True,
            "prompt_manifest_version": m.manifest_version,
            "guardrails_version": m.guardrails_version,
            "eval_baseline_sha256_prefix": bh16,
            "system_prompt": {
                "global_version": m.global_system_prompt_version,
                "global_instruction_chars": len(m.global_system_instruction_de),
            },
            "eval_regression": {
                "baseline_id": eval_baseline_id,
                "release_gate": eval_release_gate,
                "case_count": len(eval_cases_out),
                "cases": eval_cases_out,
            },
            "model_mapping": {
                "openai_model_primary": self._settings.openai_model_primary,
                "openai_model_high_reasoning": self._settings.openai_model_high_reasoning,
                "openai_model_fast": self._settings.openai_model_fast,
                "llm_openai_use_responses_api": self._settings.llm_openai_use_responses_api,
                "llm_openai_allow_chat_fallback": self._settings.llm_openai_allow_chat_fallback,
                "llm_use_fake_provider": self._settings.llm_use_fake_provider,
            },
            "orchestrator_health": {
                "status": h.get("status"),
                "fake_mode": h.get("fake_mode"),
                "openai_configured": h.get("openai_configured"),
            },
            "tasks": tasks_out,
            "eval_hint_de": (
                "Release-Sperre bei Rot: pytest tests/llm_eval (CI python-Job) "
                "und pnpm llm:eval — eval_baseline.json definiert die Case-Liste."
            ),
        }

    def run_structured(
        self,
        *,
        schema_json: dict[str, Any],
        prompt: str,
        temperature: float,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        task_type: str | None = None,
        tenant_id: str | None = None,
        provenance_retrieval_chunks: list[RetrievedChunk] | None = None,
        structured_fallback_binds: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if len(prompt) > self._settings.llm_max_prompt_chars:
            record_structured_run_outcome(task_type, "failure")
            raise LLMPromptTooLargeError(
                f"prompt_len={len(prompt)} max={self._settings.llm_max_prompt_chars}"
            )

        m_prompt = load_prompt_manifest()
        sys_de = (m_prompt.global_system_instruction_de or "").strip()

        schema_hash = stable_json_hash(schema_json)
        input_hash = stable_json_hash(
            {"temperature": temperature, "prompt": prompt, "system_de": sys_de}
        )
        pf = self._prompt_fingerprint(prompt)
        explicit_model = (model or "").strip()
        resolved_model = explicit_model or self._resolve_model_for_task(task_type)
        norm_tenant = (tenant_id or "").strip() or "unknown"
        set_llm_request_metrics(
            tenant_id=norm_tenant,
            task_type=task_type,
            model=resolved_model,
        )
        rid, cid = get_current_trace_ids()
        logger.info(
            "structured request request_id=%s correlation_id=%s pref=%s schema_hash=%s "
            "input_hash=%s prompt_fp=%s prompt_len=%s task_type=%s resolved_model=%s",
            rid or "-",
            cid or "-",
            provider_preference,
            schema_hash[:16],
            input_hash[:16],
            pf,
            len(prompt),
            task_type or "-",
            resolved_model,
        )

        try:
            chain = self._chain(provider_preference, resolved_model)
        except RuntimeError as exc:
            return self._graceful_degradation_out(
                schema_json=schema_json,
                prompt=prompt,
                task_type=task_type,
                retrieval_chunks=provenance_retrieval_chunks,
                use_model=resolved_model,
                failure_class="no_provider_configured",
                last_error=str(exc),
                llm_error_code="LLM_NO_PROVIDER_CONFIGURED",
                public_message_de=_MSG_DEGRADE_NO_PROVIDER_DE,
                schema_hash=schema_hash,
                input_hash=input_hash,
                providers_tried=[],
                structured_fallback_binds=structured_fallback_binds,
            )
        providers_tried: list[str] = []
        last_error = ""
        req_timeout_ms = self._llm_request_timeout_ms(task_type)
        deadline = time.perf_counter() + float(
            self._settings.llm_graceful_failure_deadline_sec
        )

        for prov, chain_model in chain:
            prov_key = prov.name
            use_model = chain_model
            set_llm_request_metrics(
                tenant_id=norm_tenant,
                task_type=task_type,
                model=use_model,
            )
            ckey = cache_key(
                provider=prov.name,
                model=use_model,
                schema_hash=schema_hash,
                input_hash=input_hash,
            )
            cached = self._cache.get_json(ckey)
            if cached is not None:
                try:
                    validate_against_schema(schema_json, cached)
                    validate_task_output(cached, task_type=task_type)
                except GuardrailViolation:
                    record_structured_run_outcome(task_type, "failure")
                    raise
                except SchemaValidationError as exc:
                    logger.warning("cache invalidiert: %s", exc.errors)
                    record_parsing_error(task_type, "schema_validation")
                else:
                    record_structured_run_outcome(task_type, "success")
                    return self._finalize_response(
                        {
                            "ok": True,
                            "cached": True,
                            "provider": prov.name,
                            "model": use_model,
                            "result": cached,
                        },
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                    )

            providers_tried.append(prov_key)

            if self._circuit.is_open(prov_key):
                if prov_key == "openai":
                    return self._graceful_degradation_out(
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                        use_model=use_model,
                        failure_class="circuit_open",
                        last_error="circuit_open:openai",
                        llm_error_code="LLM_PROVIDER_OFFLINE",
                        public_message_de=_MSG_DEGRADE_CIRCUIT_DE,
                        schema_hash=schema_hash,
                        input_hash=input_hash,
                        providers_tried=providers_tried,
                        structured_fallback_binds=structured_fallback_binds,
                    )
                last_error = f"circuit_open:{prov_key}"
                continue

            for attempt in range(self._settings.llm_max_retries):
                def _validate_out(obj: dict[str, Any]) -> None:
                    validate_against_schema(schema_json, obj)
                    validate_task_output(obj, task_type=task_type)

                if time.perf_counter() >= deadline:
                    return self._graceful_degradation_out(
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                        use_model=use_model,
                        failure_class="retry_exhausted",
                        last_error="deadline_exceeded",
                        llm_error_code="LLM_ORCHESTRATOR_TIMEOUT",
                        public_message_de=_MSG_DEGRADE_TIMEOUT_DE,
                        schema_hash=schema_hash,
                        input_hash=input_hash,
                        providers_tried=providers_tried,
                        structured_fallback_binds=structured_fallback_binds,
                    )
                rem_ms = int((deadline - time.perf_counter()) * 1000) - 50
                if rem_ms < 100:
                    return self._graceful_degradation_out(
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                        use_model=use_model,
                        failure_class="retry_exhausted",
                        last_error="deadline_buffer_exceeded",
                        llm_error_code="LLM_ORCHESTRATOR_TIMEOUT",
                        public_message_de=_MSG_DEGRADE_TIMEOUT_DE,
                        schema_hash=schema_hash,
                        input_hash=input_hash,
                        providers_tried=providers_tried,
                        structured_fallback_binds=structured_fallback_binds,
                    )
                call_timeout_ms = min(req_timeout_ms, rem_ms)

                raw0: dict[str, Any] | None = None
                try:
                    raw0 = prov.generate_structured(
                        schema_json,
                        prompt,
                        temperature=temperature,
                        timeout_ms=call_timeout_ms,
                        model=use_model if prov_key == "openai" else None,
                        system_instructions_de=sys_de or None,
                        task_type=task_type,
                    )
                except GuardrailViolation:
                    record_structured_run_outcome(task_type, "failure")
                    raise
                except RetryableLLMError as exc:
                    last_error = str(exc)
                    st = getattr(exc, "status_code", None)
                    if prov_key == "openai" and openai_circuit_trip_on_status(
                        st if isinstance(st, int) else None
                    ):
                        self._circuit.record_upstream_degraded(prov_key)
                    logger.warning(
                        "retryable llm error attempt=%s provider=%s: %s",
                        attempt,
                        prov_key,
                        exc,
                    )
                    if time.perf_counter() + self._backoff_duration_sec(attempt) > deadline:
                        return self._graceful_degradation_out(
                            schema_json=schema_json,
                            prompt=prompt,
                            task_type=task_type,
                            retrieval_chunks=provenance_retrieval_chunks,
                            use_model=use_model,
                            failure_class="retry_exhausted",
                            last_error=str(exc),
                            llm_error_code="LLM_ORCHESTRATOR_TIMEOUT",
                            public_message_de=_MSG_DEGRADE_TIMEOUT_DE,
                            schema_hash=schema_hash,
                            input_hash=input_hash,
                            providers_tried=providers_tried,
                            structured_fallback_binds=structured_fallback_binds,
                        )
                    sleep_backoff(
                        attempt,
                        base_sec=self._settings.llm_backoff_base_sec,
                        max_sec=self._settings.llm_backoff_max_sec,
                        jitter_ratio=self._settings.llm_backoff_jitter_ratio,
                    )
                    continue
                except Exception as exc:  # pragma: no cover - Netzwerk
                    last_error = str(exc)
                    logger.exception("provider %s failed: %s", prov_key, exc)
                    if prov_key == "openai":
                        self._circuit.record_upstream_degraded(prov_key)
                    break
                if raw0 is None:
                    continue
                last_schema: SchemaValidationError | None = None
                try:
                    _validate_out(raw0)
                except GuardrailViolation:
                    record_structured_run_outcome(task_type, "failure")
                    raise
                except SchemaValidationError as exc0:
                    last_schema = exc0
                    last_error = f"validation:{exc0.errors[:3]}"
                    record_parsing_error(task_type, "schema_validation")
                    logger.warning(
                        "schema validation (primary) attempt=%s provider=%s err=%s",
                        attempt,
                        prov_key,
                        last_error,
                    )
                else:
                    self._cache.set_json(ckey, raw0)
                    self._circuit.record_success(prov_key)
                    record_structured_run_outcome(task_type, "success")
                    return self._finalize_response(
                        {
                            "ok": True,
                            "cached": False,
                            "provider": prov.name,
                            "model": use_model,
                            "result": raw0,
                        },
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                    )

                if last_schema is not None and raw0 is not None:
                    err_txt = format_schema_errors_for_prompt(last_schema.errors)
                    schema_repair_txt = compact_schema_for_repair_prompt(schema_json)
                    repair_user = build_repair_user_prompt(
                        original_prompt=prompt,
                        invalid_json_object=raw0,
                        error_text=err_txt,
                        schema_for_repair=schema_repair_txt,
                    )
                    repair_sys = REPAIR_SYSTEM_APPEND_DE.format(error=err_txt)
                    logger.info(
                        "json self-repair: trigger task_type=%s err_preview=%s",
                        task_type or "-",
                        (last_schema.errors or [])[:2],
                    )
                    last_schema2: SchemaValidationError = last_schema
                    raw1: dict[str, Any] | None = None
                    try:
                        r2 = int((deadline - time.perf_counter()) * 1000) - 50
                        if r2 < 100:
                            return self._graceful_degradation_out(
                                schema_json=schema_json,
                                prompt=prompt,
                                task_type=task_type,
                                retrieval_chunks=provenance_retrieval_chunks,
                                use_model=use_model,
                                failure_class="retry_exhausted",
                                last_error="deadline_buffer_exceeded_repair",
                                llm_error_code="LLM_ORCHESTRATOR_TIMEOUT",
                                public_message_de=_MSG_DEGRADE_TIMEOUT_DE,
                                schema_hash=schema_hash,
                                input_hash=input_hash,
                                providers_tried=providers_tried,
                                structured_fallback_binds=structured_fallback_binds,
                            )
                        repair_timeout_ms = min(req_timeout_ms, r2)
                        raw1 = prov.generate_structured(
                            schema_json,
                            repair_user,
                            temperature=temperature,
                            timeout_ms=repair_timeout_ms,
                            model=use_model if prov_key == "openai" else None,
                            system_instructions_de=sys_de or None,
                            system_instructions_append_de=repair_sys,
                            task_type=task_type,
                        )
                    except GuardrailViolation:
                        record_structured_run_outcome(task_type, "failure")
                        raise
                    except (RetryableLLMError, Exception) as rexc:
                        last_error = str(rexc)
                        if isinstance(rexc, RetryableLLMError):
                            st2 = getattr(rexc, "status_code", None)
                            if prov_key == "openai" and openai_circuit_trip_on_status(
                                st2 if isinstance(st2, int) else None
                            ):
                                self._circuit.record_upstream_degraded(prov_key)
                        logger.warning(
                            "schema repair (llm) fehlgeschlagen attempt=%s provider=%s: %s",
                            attempt,
                            prov_key,
                            rexc,
                        )
                    if raw1 is not None:
                        try:
                            _validate_out(raw1)
                        except GuardrailViolation:
                            record_structured_run_outcome(task_type, "failure")
                            raise
                        except SchemaValidationError as exc1:
                            last_schema2 = exc1
                            last_error = f"validation:{exc1.errors[:3]}"
                            record_parsing_error(task_type, "schema_validation_repair")
                            logger.warning(
                                "schema validation (repair) failed attempt=%s: %s",
                                attempt,
                                last_error,
                            )
                        else:
                            self._cache.set_json(ckey, raw1)
                            self._circuit.record_success(prov_key)
                            record_structured_run_outcome(task_type, "success")
                            return self._finalize_response(
                                {
                                    "ok": True,
                                    "cached": False,
                                    "provider": prov.name,
                                    "model": use_model,
                                    "result": raw1,
                                },
                                schema_json=schema_json,
                                prompt=prompt,
                                task_type=task_type,
                                retrieval_chunks=provenance_retrieval_chunks,
                            )
                    # Statischer Struktur-Fallback (garantiert schema-konform, bei bekannten $id-Mappings)
                    try:
                        raw_fb = build_structured_fallback(
                            schema_json,
                            task_type=task_type,
                            last_schema_error=last_schema2,
                            fallback_binds=structured_fallback_binds,
                            repair_failure_de=format_schema_errors_for_prompt(
                                last_schema2.errors
                            ),
                        )
                        _validate_out(raw_fb)
                    except GuardrailViolation:
                        record_structured_run_outcome(task_type, "failure")
                        raise
                    except Exception as fbx:
                        last_error = f"structured_fallback:{fbx!s}"
                        record_parsing_error(task_type, "schema_fallback")
                        logger.exception(
                            "strukturierter Fallback gescheitert attempt=%s provider=%s",
                            attempt,
                            prov_key,
                        )
                        if attempt + 1 < self._settings.llm_max_retries:
                            sleep_backoff(
                                attempt,
                                base_sec=self._settings.llm_backoff_base_sec,
                                max_sec=min(
                                    self._settings.llm_backoff_max_sec,
                                    5.0,
                                ),
                                jitter_ratio=self._settings.llm_backoff_jitter_ratio,
                            )
                        continue
                    self._circuit.record_success(prov_key)
                    record_structured_run_outcome(task_type, "success")
                    return self._finalize_response(
                        {
                            "ok": True,
                            "cached": False,
                            "provider": prov.name,
                            "model": use_model,
                            "result": raw_fb,
                        },
                        schema_json=schema_json,
                        prompt=prompt,
                        task_type=task_type,
                        retrieval_chunks=provenance_retrieval_chunks,
                        provenance_extras={
                            "llm_derived": False,
                            "from_schema_fallback": True,
                            "schema_fallback_note_de": (
                                "Struktur-Fallback: Ergebnis erfüllt jsonschema, "
                                "wurde aber nicht zuverlässig vom KI-Modell erzeugt."
                            ),
                        },
                    )

        le = (last_error or "").lower()
        is_timeoutish = (
            "timeout" in le
            or "504" in le
            or "zeiti" in le
            or "deadline" in le
        )
        if is_timeoutish:
            llm_code = "LLM_ORCHESTRATOR_TIMEOUT"
            msg_de = _MSG_DEGRADE_TIMEOUT_DE
        else:
            llm_code = "LLM_UPSTREAM_FAILED"
            msg_de = _MSG_DEGRADE_UPSTREAM_DE
        fc = _classify_structured_failure(last_error)
        return self._graceful_degradation_out(
            schema_json=schema_json,
            prompt=prompt,
            task_type=task_type,
            retrieval_chunks=provenance_retrieval_chunks,
            use_model=resolved_model,
            failure_class=fc,
            last_error=last_error or "alle Provider fehlgeschlagen",
            llm_error_code=llm_code,
            public_message_de=msg_de,
            schema_hash=schema_hash,
            input_hash=input_hash,
            providers_tried=providers_tried,
            structured_fallback_binds=structured_fallback_binds,
        )

    def run_news_summary(
        self,
        *,
        title: str,
        description: str | None,
        content: str | None,
        url: str,
        source: str,
        published_ts_ms: int | None,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        body = {
            "title": title,
            "description": description,
            "content": (content or "")[:8000],
            "url": url,
            "source": source,
            "published_ts_ms": published_ts_ms,
        }
        rq = f"{title}\n{description or ''}\n{(content or '')[:2000]}"
        rchunks = self._retriever.retrieve("news_summary", rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = (
            "Du bist ein strukturierter News-Analyst fuer ein Bitget-Marktuniversum "
            "(Spot, Margin, Futures — nur soweit aus den Eingaben erkennbar). "
            "Nutze ausschliesslich Fakten aus EINGABE und RETRIEVAL. Erfinde keine Boersen, "
            "keine Listings und keine Zahlen, die nicht implizit oder explizit genannt sind.\n\n"
            f"RETRIEVAL:\n{rag}\n\nEINGABE:\n{json.dumps(body, ensure_ascii=False, indent=2)}"
        )
        return self.run_structured(
            schema_json=self._news_schema,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="news_summary",
            provenance_retrieval_chunks=rchunks,
        )

    def _trunc_json(self, obj: Any, max_chars: int = 12_000) -> str:
        raw = json.dumps(obj, ensure_ascii=False, default=str)
        if len(raw) <= max_chars:
            return raw
        return raw[:max_chars] + "\n…"

    def run_analyst_hypotheses(
        self,
        *,
        context_json: dict[str, Any],
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.15,
    ) -> dict[str, Any]:
        q = self._trunc_json(context_json)
        rchunks = self._retriever.retrieve("analyst_hypotheses", q)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = (
            "Extrahiere pruefbare Hypothesen aus dem Kontext. "
            "Keine Handlungsempfehlung, keine Orderparameter. "
            "Antworte nur als JSON gemaess Schema.\n\n"
            f"RETRIEVAL:\n{rag}\n\nKONTEXT_JSON:\n{q}"
        )
        return self.run_structured(
            schema_json=self._schema_hypotheses,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="analyst_hypotheses",
            provenance_retrieval_chunks=rchunks,
        )

    def run_analyst_context_classification(
        self,
        *,
        narrative_de: str,
        instrument_hint: str | None = None,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.15,
    ) -> dict[str, Any]:
        q = f"{instrument_hint or ''}\n{narrative_de}"[:14_000]
        rchunks = self._retriever.retrieve("analyst_context_classification", q)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = (
            "Klassifiziere den marktlichen Kontext (Kategorien nur aus dem Schema). "
            "Bewerte Konflikt zur rein technischen Sicht; Facetten-Hints sind Vorschlaege, "
            "keine autoritative SMC-Zuordnung.\n\n"
            f"RETRIEVAL:\n{rag}\n\nNARRATIV:\n{q}"
        )
        return self.run_structured(
            schema_json=self._schema_context_cls,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="analyst_context_classification",
            provenance_retrieval_chunks=rchunks,
        )

    def run_post_trade_review(
        self,
        *,
        trade_facts_json: dict[str, Any],
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        q = self._trunc_json(trade_facts_json)
        rchunks = self._retriever.retrieve("post_trade_review", q)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = (
            "Post-Trade-Review: vergleiche Plan vs. Outcome. "
            "Keine neuen Strategieparameter, keine Rueckmeldung an Risk-Limits.\n\n"
            f"RETRIEVAL:\n{rag}\n\nTRADE_FACTS_JSON:\n{q}"
        )
        return self.run_structured(
            schema_json=self._schema_post_trade,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="post_trade_review",
            provenance_retrieval_chunks=rchunks,
        )

    def run_operator_explain(
        self,
        *,
        question_de: str,
        readonly_context_json: dict[str, Any],
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
        execution_id: UUID | None = None,
    ) -> dict[str, Any]:
        ro = (
            copy.deepcopy(readonly_context_json)
            if isinstance(readonly_context_json, dict)
            else {}
        )
        try:
            fetched = fetch_onchain_macro_context(self._settings.redis_url)
            ro = merge_fetched_onchain_into_context(ro, fetched)
        except Exception as exc:
            logger.warning("operator_explain: onchain_macro fetch: %s", exc)
        qctx = format_operator_readonly_pro_symbol(
            ro, max_total_chars=10_000
        )
        rq = f"{question_de}\n{qctx}"
        rchunks = self._retriever.retrieve("operator_explain", rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = build_operator_explain_user_prompt(
            question_de=question_de,
            readonly_context_json_text=qctx,
            retrieval_block=rag,
        )
        tid = extract_tenant_id_from_object(ro)
        out = self.run_structured(
            schema_json=self._schema_operator_explain,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="operator_explain",
            tenant_id=tid,
            provenance_retrieval_chunks=rchunks,
        )
        if execution_id is not None:
            persist_operator_explain_row(
                self._settings,
                execution_id=execution_id,
                response=out,
            )
        return out

    def run_safety_incident_diagnosis(
        self,
        *,
        question_de: str,
        diagnostic_context_json: dict[str, Any],
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        qctx = self._trunc_json(diagnostic_context_json, max_chars=14_000)
        rq = f"{question_de}\n{qctx}"
        rchunks = self._retriever.retrieve("safety_incident_diagnosis", rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = build_safety_incident_diagnosis_user_prompt(
            question_de=question_de,
            diagnostic_context_json_text=qctx,
            retrieval_block=rag,
        )
        return self.run_structured(
            schema_json=self._schema_safety_incident_diagnosis,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="safety_incident_diagnosis",
            provenance_retrieval_chunks=rchunks,
        )

    def run_strategy_signal_explain(
        self,
        *,
        signal_context_json: dict[str, Any],
        focus_question_de: str | None,
        execution_id: Any | None = None,
        source_signal_id: Any | None = None,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        sctx = self._trunc_json(signal_context_json, max_chars=12_000)
        fq = (focus_question_de or "").strip()
        rq = f"{fq}\n{sctx}" if fq else sctx
        rchunks = self._retriever.retrieve("strategy_signal_explain", rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = build_strategy_signal_explain_user_prompt(
            signal_context_json_text=sctx,
            focus_question_de=fq,
            retrieval_block=rag,
        )
        out = self.run_structured(
            schema_json=self._schema_strategy_signal_explain,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="strategy_signal_explain",
            provenance_retrieval_chunks=rchunks,
        )
        res = out.get("result")
        if isinstance(res, dict):
            exs = (res.get("expected_scenario_de") or "").strip()
            if not exs:
                src = (res.get("strategy_explanation_de") or "").strip()
                res["expected_scenario_de"] = (src[:2000] if src else "—")
            ca = res.get("chart_annotations")
            if ca is not None:
                fixed, n_ms_fix = sanitize_strategy_chart_annotations(ca)
                res["chart_annotations"] = fixed
                if n_ms_fix > 0:
                    prov = out.get("provenance")
                    if isinstance(prov, dict):
                        prov["chart_annotation_unix_ms_corrected"] = n_ms_fix
        ex_u: UUID | None = execution_id if isinstance(execution_id, UUID) else None
        sig_u: UUID | None = source_signal_id if isinstance(source_signal_id, UUID) else None
        if ex_u is None and sig_u is None and isinstance(signal_context_json, dict):
            raw = signal_context_json.get("signal_id")
            if raw is not None:
                try:
                    sig_u = UUID(str(raw))
                except (TypeError, ValueError):
                    pass
        if ex_u is not None or sig_u is not None:
            persist_strategy_signal_explain_row(
                self._settings,
                response=out,
                execution_id=ex_u,
                source_signal_id=sig_u,
            )
        return out

    def run_ai_strategy_proposal_draft(
        self,
        *,
        chart_context_json: dict[str, Any],
        focus_question_de: str | None,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        cctx = self._trunc_json(chart_context_json, max_chars=12_000)
        fq = (focus_question_de or "").strip()
        rq = f"{fq}\n{cctx}" if fq else cctx
        rchunks = self._retriever.retrieve("ai_strategy_proposal_draft", rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = build_ai_strategy_proposal_draft_user_prompt(
            chart_context_json_text=cctx,
            focus_question_de=fq,
            retrieval_block=rag,
        )
        out = self.run_structured(
            schema_json=self._schema_ai_strategy_proposal_draft,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="ai_strategy_proposal_draft",
            provenance_retrieval_chunks=rchunks,
        )
        res = out.get("result")
        if isinstance(res, dict):
            res["execution_authority"] = "none"
            ca = res.get("chart_annotations")
            if ca is not None:
                fixed, n_ms_fix = sanitize_strategy_chart_annotations(ca)
                res["chart_annotations"] = fixed
                if n_ms_fix > 0:
                    prov = out.get("provenance")
                    if isinstance(prov, dict):
                        prov["chart_annotation_unix_ms_corrected"] = n_ms_fix
        return out

    def run_assistant_turn(
        self,
        *,
        assist_role: str,
        conversation_id: str,
        tenant_partition_id: str,
        user_message_de: str,
        context_json: dict[str, Any],
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        task_type = task_type_for_role(assist_role)
        filtered = filter_context_for_role(assist_role, context_json)
        hist = self._assist_conv.load_history(
            partition_id=tenant_partition_id,
            assist_role=assist_role,
            conversation_id=conversation_id,
        )
        qctx = self._trunc_json(filtered, max_chars=14_000)
        hist_digest = "\n".join(
            (m.get("content_de") or "")[:400] for m in hist[-8:]
        )
        rq = f"{user_message_de}\n{qctx}\n{hist_digest}"
        rchunks = self._retriever.retrieve(task_type, rq)
        rag = self._retriever.format_for_prompt(rchunks)
        prompt = build_assistant_turn_user_prompt(
            task_type=task_type,
            assist_role=assist_role,
            history_messages=hist,
            user_message_de=user_message_de,
            server_context_json_text=qctx,
            retrieval_block=rag,
        )
        schema_dyn = copy.deepcopy(self._schema_assistant_turn_base)
        props = schema_dyn.setdefault("properties", {})
        props["assist_role_echo"] = {"type": "string", "const": assist_role}
        out = self.run_structured(
            schema_json=schema_dyn,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type=task_type,
            tenant_id=tenant_partition_id,
            provenance_retrieval_chunks=rchunks,
            structured_fallback_binds={"assist_role_echo": assist_role},
        )
        reply = str(out.get("result", {}).get("assistant_reply_de") or "")
        hist_after = self._assist_conv.append_exchange(
            partition_id=tenant_partition_id,
            assist_role=assist_role,
            conversation_id=conversation_id,
            user_message_de=user_message_de.strip(),
            assistant_reply_de=reply,
        )
        out["assist_session"] = {
            "conversation_id": conversation_id,
            "tenant_partition_id": tenant_partition_id,
            "assist_role": assist_role,
            "history_message_count": len(hist_after),
        }
        return out

    def run_strategy_journal_summary(
        self,
        *,
        journal_events_json: list[Any] | dict[str, Any],
        period_label_de: str | None = None,
        provider_preference: ProviderPref = "auto",
        model: str | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        q = self._trunc_json(
            {"period_label_de": period_label_de, "events": journal_events_json},
            max_chars=14_000,
        )
        rchunks = self._retriever.retrieve("strategy_journal_summary", q)
        rag = self._retriever.format_for_prompt(rchunks)
        pl = period_label_de or "unspezifiziert"
        prompt = (
            "Fasse Strategie-Journal-Ereignisse fuer Operatoren zusammen. "
            "Nur deskriptiv; keine Parameteraenderungen.\n\n"
            f"RETRIEVAL:\n{rag}\n\nZEITRAUM_LABEL: {pl}\n\nEVENTS_JSON:\n{q}"
        )
        return self.run_structured(
            schema_json=self._schema_journal,
            prompt=prompt,
            temperature=temperature,
            provider_preference=provider_preference,
            model=model,
            task_type="strategy_journal_summary",
            provenance_retrieval_chunks=rchunks,
        )
