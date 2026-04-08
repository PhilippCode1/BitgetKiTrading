"""
Kanonsicher Vertrag fuer die KI-Schicht (Modul Mate GmbH).

Bezug: docs/AI_LAYER_ARCHITECTURE_MODUL_MATE.md (Prompt 3).

Zweck:
- Klare Trennung: Nutzeranfrage, Fachlogik, KI-Inferenz, Trading-Policy, Ausfuehrung, Audit.
- Stabile IDs fuer Prompt-Registry, Modell-Routing und Traces — unabhaengig vom konkreten Provider.
- Vorbereitung auf spaetere OpenAI-Modelle, Tools und Guardrails ohne Zerstreuung in der App.

Hinweis: Der Dienst `services/llm-orchestrator` implementiert Inferenz + Validierung; dieses Modul
definiert die uebergreifenden Begriffe. Kommerzielle Gates liegen in `product_policy` / `customer_lifecycle`
und duerfen **niemals** aus Modellantworten abgeleitet werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

AI_LAYER_CONTRACT_VERSION = "1.0.0"
AI_ARCHITECTURE_DOCUMENT_ID = "AI_LAYER_ARCHITECTURE_MODUL_MATE"


class PipelineStage(str, Enum):
    """
    Verarbeitungsphasen von aussen nach innen und zurueck zur Antwort.

    Reihenfolge-Pflicht fuer schreibende Trading-Pfade: steigende Werte bis EXECUTION,
    danach AUDIT_LOG.
    """

    USER_REQUEST = "user_request"
    DOMAIN_CONTEXT = "domain_context"
    AI_INFERENCE = "ai_inference"
    TRADING_POLICY = "trading_policy"
    EXECUTION = "execution"
    AUDIT_LOG = "audit_log"


_PIPELINE_ORDER: dict[PipelineStage, int] = {
    PipelineStage.USER_REQUEST: 10,
    PipelineStage.DOMAIN_CONTEXT: 20,
    PipelineStage.AI_INFERENCE: 30,
    PipelineStage.TRADING_POLICY: 40,
    PipelineStage.EXECUTION: 50,
    PipelineStage.AUDIT_LOG: 60,
}


def pipeline_stage_rank(stage: PipelineStage) -> int:
    """Numerische Ordnung fuer Validierungen."""
    return _PIPELINE_ORDER[stage]


def assert_monotonic_pipeline(stages: list[PipelineStage]) -> None:
    """
    Prueft, ob die Liste die erwartete Pipeline-Reihenfolge einhaelt (monoton nicht fallend).

    Raises:
        ValueError: bei Verletzung (z. B. EXECUTION vor TRADING_POLICY).
    """
    if len(stages) < 2:
        return
    last = pipeline_stage_rank(stages[0])
    for s in stages[1:]:
        r = pipeline_stage_rank(s)
        if r < last:
            raise ValueError(f"Pipeline out of order: {stages!r}")
        last = r


class PromptRegistryKey(str, Enum):
    """
    Stabile Schluessel fuer Prompt-Templates (Admin-Registry, Versionierung in DB).

    Bestehende LLM-Orchestrator-Aufgaben sind eingetragen; Webapp-spezifische Erweiterungen
    folgen ohne Umbenennung der Kernschluessel.
    """

    NEWS_SUMMARY = "news_summary"
    ANALYST_HYPOTHESES = "analyst_hypotheses"
    ANALYST_CONTEXT_CLASSIFICATION = "analyst_context_classification"
    POST_TRADE_REVIEW = "post_trade_review"
    OPERATOR_EXPLAIN = "operator_explain"
    STRATEGY_JOURNAL_SUMMARY = "strategy_journal_summary"
    STRUCTURED_ADHOC = "structured_adhoc"
    # Webapp / Kunde (spaeter; Platzhalter fuer Registry)
    CUSTOMER_MARKET_NARRATIVE = "customer_market_narrative"
    CUSTOMER_RISK_EXPLAINER = "customer_risk_explainer"


# Alle Keys sind grundsaetzlich admin-konfigurierbar (Text, Modell-Profil, Ausgabe-Schema-Referenz).
ADMIN_VERSIONED_PROMPT_KEYS: frozenset[PromptRegistryKey] = frozenset(PromptRegistryKey)


class ModelRoutingProfile(str, Enum):
    """Grobes Modell-Routing — konkrete Modell-IDs bleiben Konfiguration/ENV."""

    ECONOMY = "economy"
    STANDARD = "standard"
    REASONING = "reasoning"


class GuardrailLevel(str, Enum):
    """Sicherheitsstufe fuer Inferenz (Tools, Freitext-Laenge, Autonomie)."""

    STRICT = "strict"
    NORMAL = "normal"
    INTERNAL_RESEARCH = "internal_research"


class FallbackStrategy(str, Enum):
    """Reaktion wenn die KI-Schicht ausfaellt oder Antworten ungueltig sind."""

    FULL = "full"
    DEGRADED_CACHED = "degraded_cached"
    STATIC_MESSAGE = "static_message"
    AI_PAUSED = "ai_paused"


@dataclass(frozen=True)
class RateLimitPolicy:
    """Richtwerte fuer Services (kein Enforcement hier)."""

    requests_per_minute_per_user: int = 30
    requests_per_minute_global: int = 5_000
    max_prompt_chars_default: int = 48_000
    max_output_tokens_default: int = 4_096
    daily_token_budget_per_user: int = 500_000


DEFAULT_RATE_LIMIT_POLICY = RateLimitPolicy()


@dataclass(frozen=True)
class InferenceRequestMeta:
    """Metadaten fuer Schicht 2–3 (ohne Prompt-Rohinhalt)."""

    trace_id: str
    prompt_registry_key: PromptRegistryKey
    prompt_version_id: str
    model_profile: ModelRoutingProfile
    guardrail_level: GuardrailLevel
    customer_account_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class InferenceResultMeta:
    """Metadaten nach Schicht 3 (ohne Modellrohtext-Pflicht)."""

    trace_id: str
    prompt_registry_key: PromptRegistryKey
    prompt_version_id: str
    model_id: str
    provider: str
    schema_id: str | None
    prompt_fingerprint_sha256: str | None
    cached: bool
    llm_derived: Literal[True] = True


@dataclass(frozen=True)
class TradingDecisionEnvelope:
    """
    Ergebnis der Trading-Policy (Schicht 4): strukturierter Befehl oder Ablehnung.

    `command` ist ein Service-spezifisches Dict; Typisierung erfolgt in Broker-Gateways.
    """

    trace_id: str
    allowed: bool
    reject_reason_code: str | None = None
    command: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionReceipt:
    """Schicht 5 — minimale Quittung fuer Audit."""

    trace_id: str
    execution_mode: Literal["demo", "live", "none"]
    client_order_id: str | None = None
    exchange_order_id: str | None = None
    status: str = "unknown"


@dataclass(frozen=True)
class AuditEventStub:
    """Schicht 6 — ein Eintrag in der Ereigniskette (Append-only)."""

    trace_id: str
    stage: PipelineStage
    event_type: str
    payload_redacted: dict[str, Any] = field(default_factory=dict)


class MemoryScope(str, Enum):
    """Platzhalter fuer spaeteres Nutzer-Gedaechtnis / RAG (keine Implementierung hier)."""

    SESSION = "session"
    USER_FACTS = "user_facts"
    RAG_CORPUS = "rag_corpus"


def suggest_fallback_strategy(
    *,
    provider_reachable: bool,
    schema_valid: bool,
    circuit_open: bool,
    admin_ai_paused: bool,
) -> FallbackStrategy:
    """
    Einfache Prioritaetskette fuer Support und Gateway-Entscheidungen.

    [ANNAHME] Reihenfolge: Admin-Pause > Circuit > Schema > Provider.
    """
    if admin_ai_paused:
        return FallbackStrategy.AI_PAUSED
    if circuit_open or not provider_reachable:
        return FallbackStrategy.DEGRADED_CACHED
    if not schema_valid:
        return FallbackStrategy.STATIC_MESSAGE
    return FallbackStrategy.FULL


def trading_execution_requires_prior_policy(receipt: ExecutionReceipt, policy: TradingDecisionEnvelope) -> bool:
    """
    Prueft konsistente trace_id und dass Ausfuehrung nicht ohne erlaubte Policy erfolgt.

    Services sollen vor EXECUTION einen TradingDecisionEnvelope persistieren/validieren.
    """
    if receipt.trace_id != policy.trace_id:
        return False
    if receipt.execution_mode == "none":
        return True
    return policy.allowed is True


def ai_layer_descriptor() -> dict[str, str | int]:
    return {
        "ai_layer_contract_version": AI_LAYER_CONTRACT_VERSION,
        "ai_architecture_document_id": AI_ARCHITECTURE_DOCUMENT_ID,
        "pipeline_stages": len(PipelineStage),
        "prompt_registry_keys": len(PromptRegistryKey),
    }
