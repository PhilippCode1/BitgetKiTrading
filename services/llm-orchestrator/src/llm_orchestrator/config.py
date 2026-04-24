from __future__ import annotations

from typing import ClassVar, Literal

from config.settings import BaseServiceSettings, _is_blank_or_placeholder
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict


class LLMOrchestratorSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("redis_url",)
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields + ("redis_url",)
    )

    redis_url: str = Field(alias="REDIS_URL")
    llm_orch_port: int = Field(default=8070, alias="LLM_ORCH_PORT")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model_primary: str = Field(default="gpt-5.4", alias="OPENAI_MODEL_PRIMARY")
    openai_model_high_reasoning: str = Field(
        default="gpt-5.4-pro",
        alias="OPENAI_MODEL_HIGH_REASONING",
        description="Schwere Erklaerungs-/Operator-Tasks (Structured Outputs).",
    )
    openai_model_fast: str = Field(
        default="gpt-4o-mini",
        alias="OPENAI_MODEL_FAST",
        description="Schnelle/kostenguenstige Tasks (z. B. News-Zusammenfassung).",
    )
    llm_openai_use_responses_api: bool = Field(
        default=True,
        alias="LLM_OPENAI_USE_RESPONSES_API",
        description=(
            "Structured Outputs primaer ueber /v1/responses (OpenAI SDK >= 2.8)."
        ),
    )
    llm_openai_allow_chat_fallback: bool = Field(
        default=False,
        alias="LLM_OPENAI_ALLOW_CHAT_FALLBACK",
        description=(
            "Bei Responses-/Schema-Fehlern auf Chat Completions json_schema "
            "zurueckfallen (nur local/development/test empfohlen; "
            "in shadow/production verboten)."
        ),
    )

    llm_cache_ttl_sec: int = Field(default=3600, alias="LLM_CACHE_TTL_SEC")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_timeout_ms: int = Field(default=30_000, alias="LLM_TIMEOUT_MS")
    llm_request_timeout_ms_fast: int = Field(
        default=10_000,
        alias="LLM_REQUEST_TIMEOUT_MS_FAST",
        description="Timeout ms fuer schnelle Tasks (news, kurze Klassifikation).",
    )
    llm_request_timeout_ms_deep: int = Field(
        default=30_000,
        alias="LLM_REQUEST_TIMEOUT_MS_DEEP",
        description="Timeout ms fuer lange/Reasoning-Tasks (z. B. operator_explain).",
    )
    llm_use_fake_provider: bool = Field(default=False, alias="LLM_USE_FAKE_PROVIDER")
    llm_max_prompt_chars: int = Field(default=48_000, alias="LLM_MAX_PROMPT_CHARS")

    llm_backoff_base_sec: float = Field(default=0.5, alias="LLM_BACKOFF_BASE_SEC")
    llm_backoff_max_sec: float = Field(default=30.0, alias="LLM_BACKOFF_MAX_SEC")
    llm_backoff_jitter_ratio: float = Field(
        default=0.0,
        alias="LLM_BACKOFF_JITTER_RATIO",
    )
    llm_circuit_fail_threshold: int = Field(
        default=3, alias="LLM_CIRCUIT_FAIL_THRESHOLD"
    )
    llm_circuit_window_sec: int = Field(
        default=60,
        alias="LLM_CIRCUIT_WINDOW_SEC",
        description="Schiebefenster-Sekunden fuer 5xx/Timeout-Zaehlung.",
    )
    llm_circuit_open_sec: int = Field(default=60, alias="LLM_CIRCUIT_OPEN_SEC")

    llm_graceful_failure_deadline_sec: float = Field(
        default=5.0,
        alias="LLM_GRACEFUL_FAILURE_DEADLINE_SEC",
        description=(
            "Max. Wandzeit (s) bis Graceful-Degradation in run_structured "
            "(Fail-Closed, Antwort per HTTP 200)."
        ),
    )

    llm_knowledge_max_chunks: int = Field(
        default=4,
        alias="LLM_KNOWLEDGE_MAX_CHUNKS",
        description=(
            "Max. kuratierte Ausschnitte aus docs/llm_knowledge pro Analyst-Call "
            "(0=aus)."
        ),
    )
    llm_knowledge_excerpt_chars: int = Field(
        default=2800,
        alias="LLM_KNOWLEDGE_EXCERPT_CHARS",
        description="Zeichen pro Ausschnitt (harter Cap gegen Prompt-Bloat).",
    )

    llm_assist_conversation_ttl_sec: int = Field(
        default=86_400,
        alias="LLM_ASSIST_CONVERSATION_TTL_SEC",
        description="Redis-TTL fuer Assistenz-Dialoge (Sekunden).",
    )
    llm_assist_max_history_messages: int = Field(
        default=24,
        alias="LLM_ASSIST_MAX_HISTORY_MESSAGES",
        description="Max. gespeicherte Verlaufs-Nachrichten (user+assistant) pro Konversation.",
    )

    feature_engine_base_url: str = Field(
        default="http://127.0.0.1:8020",
        alias="FEATURE_ENGINE_BASE_URL",
        description="Basis-URL der Feature-Engine fuer Quant-Analyst im War-Room.",
    )
    war_room_agent_timeout_sec: float = Field(
        default=25.0,
        alias="WAR_ROOM_AGENT_TIMEOUT_SEC",
        description="Pro-Agent-Timeout (asyncio.wait_for) fuer den ConsensusOrchestrator.",
    )
    learning_engine_base_url: str = Field(
        default="http://127.0.0.1:8090",
        alias="LEARNING_ENGINE_BASE_URL",
        description="Basis-URL learning-engine fuer TimesFM/War-Room-Audit (optional).",
    )
    tsfm_learning_feedback_enabled: bool = Field(
        default=True,
        alias="TSFM_LEARNING_FEEDBACK_ENABLED",
        description="Nach War-Room POST /learning/tsfm-war-room-audit (async, best-effort).",
    )
    war_room_fetch_specialist_precision: bool = Field(
        default=True,
        alias="WAR_ROOM_FETCH_SPECIALIST_PRECISION",
        description="GET /learning/war-room/specialist-ai-precision (dynam. Gewichte, Prompt 29).",
    )
    war_room_specialist_precision_timeout_sec: float = Field(
        default=2.0,
        ge=0.2,
        le=15.0,
        alias="WAR_ROOM_SPECIALIST_PRECISION_TIMEOUT_SEC",
    )
    audit_ledger_base_url: str = Field(
        default="",
        alias="AUDIT_LEDGER_BASE_URL",
        description="Basis-URL des audit-ledger Microservice (War-Room-Commit vor Antwort).",
    )
    audit_ledger_commit_required: bool = Field(
        default=False,
        alias="AUDIT_LEDGER_COMMIT_REQUIRED",
        description="Wenn true: ohne erfolgreichen Ledger-Commit keine War-Room-Antwort.",
    )

    risk_governor_ams_mode: Literal["live", "simulation", "off"] = Field(
        default="live",
        alias="RISK_GOVERNOR_AMS_MODE",
        description="live=Veto-Eskalation bei hoher AMS-Toxizitaet; simulation=nur Eval im Payload; off=aus.",
    )
    risk_governor_toxicity_model_path: str | None = Field(
        default=None,
        alias="RISK_GOVERNOR_TOXICITY_MODEL_PATH",
        description="joblib RandomForest (gleiche Features wie AMS-Trainingspfad).",
    )
    risk_governor_toxicity_veto_threshold_0_1: float = Field(
        default=0.66,
        ge=0.0,
        le=1.0,
        alias="RISK_GOVERNOR_TOXICITY_VETO_THRESHOLD_0_1",
    )
    risk_governor_vpin_mode: Literal["live", "simulation", "off"] = Field(
        default="live",
        alias="RISK_GOVERNOR_VPIN_MODE",
        description="live=VPIN-Hard-Veto bei hohem Orderflow-Toxizitaets-Score; simulation=nur Eval; off=aus.",
    )
    risk_governor_vpin_veto_threshold_0_1: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        alias="RISK_GOVERNOR_VPIN_VETO_THRESHOLD_0_1",
        description="Schwelle fuer VPIN/Toxizitaet aus market-stream (context vpin_toxicity_0_1).",
    )

    eventbus_dedupe_ttl_sec: int = Field(default=0, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    llm_ai_evaluation_log_enabled: bool = Field(
        default=True,
        alias="LLM_AI_EVAL_LOG_ENABLED",
        description="operator_explain mit execution_id in public.ai_evaluation_logs persistieren (DATABASE_URL).",
    )

    @field_validator("llm_orch_port")
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("LLM_ORCH_PORT ungueltig")
        return v

    @field_validator("llm_max_retries")
    @classmethod
    def _retries(cls, v: int) -> int:
        if v < 1:
            raise ValueError("LLM_MAX_RETRIES muss >= 1 sein")
        return v

    @field_validator("llm_timeout_ms")
    @classmethod
    def _timeout_ms(cls, v: int) -> int:
        if v < 1_000:
            raise ValueError("LLM_TIMEOUT_MS muss mindestens 1000 (1s) sein")
        if v > 600_000:
            raise ValueError("LLM_TIMEOUT_MS ueberschreitet 600000 (10 Minuten)")
        return v

    @field_validator("llm_request_timeout_ms_fast")
    @classmethod
    def _req_fast_ms(cls, v: int) -> int:
        if v < 1_000 or v > 120_000:
            raise ValueError("LLM_REQUEST_TIMEOUT_MS_FAST muss 1000..120000 sein")
        return v

    @field_validator("llm_request_timeout_ms_deep")
    @classmethod
    def _req_deep_ms(cls, v: int) -> int:
        if v < 3_000 or v > 120_000:
            raise ValueError("LLM_REQUEST_TIMEOUT_MS_DEEP muss 3000..120000 sein")
        return v

    @field_validator("llm_circuit_window_sec")
    @classmethod
    def _circuit_window(cls, v: int) -> int:
        if v < 5 or v > 3_600:
            raise ValueError("LLM_CIRCUIT_WINDOW_SEC muss 5..3600 sein")
        return v

    @field_validator("llm_graceful_failure_deadline_sec")
    @classmethod
    def _graceful_deadline_sec(cls, v: float) -> float:
        if v < 0.5 or v > 60.0:
            raise ValueError("LLM_GRACEFUL_FAILURE_DEADLINE_SEC muss 0.5..60 sein")
        return v

    @field_validator("llm_max_prompt_chars")
    @classmethod
    def _prompt_cap(cls, v: int) -> int:
        if v < 256:
            raise ValueError("LLM_MAX_PROMPT_CHARS muss >= 256 sein")
        if v > 512_000:
            raise ValueError("LLM_MAX_PROMPT_CHARS ungueltig gross")
        return v

    @field_validator("llm_backoff_jitter_ratio")
    @classmethod
    def _jitter_ratio(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("LLM_BACKOFF_JITTER_RATIO muss 0..1 sein")
        return v

    @field_validator("llm_knowledge_max_chunks")
    @classmethod
    def _k_chunks(cls, v: int) -> int:
        if v < 0 or v > 24:
            raise ValueError("LLM_KNOWLEDGE_MAX_CHUNKS muss 0..24 sein")
        return v

    @field_validator("llm_knowledge_excerpt_chars")
    @classmethod
    def _k_excerpt(cls, v: int) -> int:
        if v < 200 or v > 32_000:
            raise ValueError("LLM_KNOWLEDGE_EXCERPT_CHARS ausserhalb erlaubtem Bereich")
        return v

    @field_validator("llm_assist_max_history_messages")
    @classmethod
    def _assist_hist_cap(cls, v: int) -> int:
        if v < 2 or v > 200:
            raise ValueError("LLM_ASSIST_MAX_HISTORY_MESSAGES muss 2..200 sein")
        return v

    @field_validator("war_room_agent_timeout_sec")
    @classmethod
    def _war_room_timeout(cls, v: float) -> float:
        x = float(v)
        if not 1.0 <= x <= 120.0:
            raise ValueError("WAR_ROOM_AGENT_TIMEOUT_SEC muss zwischen 1 und 120 liegen")
        return x

    @model_validator(mode="after")
    def _llm_timeouts_and_circuit(self) -> LLMOrchestratorSettings:
        if self.llm_request_timeout_ms_fast > self.llm_request_timeout_ms_deep:
            raise ValueError(
                "LLM_REQUEST_TIMEOUT_MS_FAST muss <= LLM_REQUEST_TIMEOUT_MS_DEEP sein"
            )
        return self

    @model_validator(mode="after")
    def _validate_provider_requirements(self) -> LLMOrchestratorSettings:
        if self.llm_use_fake_provider and self.app_env in ("shadow", "production"):
            raise ValueError(
                "LLM_USE_FAKE_PROVIDER=true ist fuer APP_ENV shadow/production verboten"
            )
        if (
            self.app_env in ("shadow", "production")
            and self.llm_openai_allow_chat_fallback
        ):
            raise ValueError(
                "LLM_OPENAI_ALLOW_CHAT_FALLBACK=true ist fuer APP_ENV "
                "shadow/production verboten"
            )
        if not self.production or self.llm_use_fake_provider:
            return self
        if _is_blank_or_placeholder(self.openai_api_key or ""):
            raise ValueError(
                "OPENAI_API_KEY muss fuer Produktion gesetzt sein (kein Fake-Provider)"
            )
        return self
