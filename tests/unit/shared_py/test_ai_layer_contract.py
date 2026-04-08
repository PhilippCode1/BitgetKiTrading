"""Tests fuer shared_py.ai_layer_contract (Prompt 3)."""

from __future__ import annotations

import pytest

from shared_py.ai_layer_contract import (
    AI_LAYER_CONTRACT_VERSION,
    DEFAULT_RATE_LIMIT_POLICY,
    ExecutionReceipt,
    FallbackStrategy,
    GuardrailLevel,
    InferenceRequestMeta,
    MemoryScope,
    ModelRoutingProfile,
    PipelineStage,
    PromptRegistryKey,
    TradingDecisionEnvelope,
    ADMIN_VERSIONED_PROMPT_KEYS,
    ai_layer_descriptor,
    assert_monotonic_pipeline,
    pipeline_stage_rank,
    suggest_fallback_strategy,
    trading_execution_requires_prior_policy,
)


def test_pipeline_order_increasing() -> None:
    assert pipeline_stage_rank(PipelineStage.USER_REQUEST) < pipeline_stage_rank(PipelineStage.EXECUTION)


def test_assert_monotonic_ok() -> None:
    assert_monotonic_pipeline(
        [
            PipelineStage.USER_REQUEST,
            PipelineStage.DOMAIN_CONTEXT,
            PipelineStage.AI_INFERENCE,
            PipelineStage.TRADING_POLICY,
            PipelineStage.EXECUTION,
            PipelineStage.AUDIT_LOG,
        ]
    )


def test_assert_monotonic_fails() -> None:
    with pytest.raises(ValueError, match="out of order"):
        assert_monotonic_pipeline(
            [
                PipelineStage.EXECUTION,
                PipelineStage.TRADING_POLICY,
            ]
        )


def test_suggest_fallback_admin_pause() -> None:
    assert (
        suggest_fallback_strategy(
            provider_reachable=True,
            schema_valid=True,
            circuit_open=False,
            admin_ai_paused=True,
        )
        == FallbackStrategy.AI_PAUSED
    )


def test_suggest_fallback_circuit() -> None:
    assert (
        suggest_fallback_strategy(
            provider_reachable=True,
            schema_valid=True,
            circuit_open=True,
            admin_ai_paused=False,
        )
        == FallbackStrategy.DEGRADED_CACHED
    )


def test_suggest_fallback_schema() -> None:
    assert (
        suggest_fallback_strategy(
            provider_reachable=True,
            schema_valid=False,
            circuit_open=False,
            admin_ai_paused=False,
        )
        == FallbackStrategy.STATIC_MESSAGE
    )


def test_suggest_fallback_full() -> None:
    assert (
        suggest_fallback_strategy(
            provider_reachable=True,
            schema_valid=True,
            circuit_open=False,
            admin_ai_paused=False,
        )
        == FallbackStrategy.FULL
    )


def test_trading_execution_requires_policy() -> None:
    tid = "trace-1"
    pol = TradingDecisionEnvelope(trace_id=tid, allowed=True, command={"x": 1})
    rec = ExecutionReceipt(trace_id=tid, execution_mode="live", status="submitted")
    assert trading_execution_requires_prior_policy(rec, pol) is True


def test_trading_execution_rejects_mismatched_trace() -> None:
    pol = TradingDecisionEnvelope(trace_id="a", allowed=True)
    rec = ExecutionReceipt(trace_id="b", execution_mode="live")
    assert trading_execution_requires_prior_policy(rec, pol) is False


def test_trading_execution_none_without_allow() -> None:
    pol = TradingDecisionEnvelope(trace_id="t", allowed=False)
    rec = ExecutionReceipt(trace_id="t", execution_mode="none")
    assert trading_execution_requires_prior_policy(rec, pol) is True


def test_prompt_keys_versioned() -> None:
    assert PromptRegistryKey.NEWS_SUMMARY in ADMIN_VERSIONED_PROMPT_KEYS


def test_inference_meta_frozen() -> None:
    m = InferenceRequestMeta(
        trace_id="1",
        prompt_registry_key=PromptRegistryKey.OPERATOR_EXPLAIN,
        prompt_version_id="v3",
        model_profile=ModelRoutingProfile.STANDARD,
        guardrail_level=GuardrailLevel.STRICT,
    )
    assert m.prompt_version_id == "v3"


def test_live_execution_requires_allowed_policy() -> None:
    tid = "trace-x"
    pol = TradingDecisionEnvelope(trace_id=tid, allowed=False, reject_reason_code="limit")
    rec = ExecutionReceipt(trace_id=tid, execution_mode="live")
    assert trading_execution_requires_prior_policy(rec, pol) is False


def test_memory_scope_exists() -> None:
    assert MemoryScope.SESSION.value == "session"


def test_descriptor() -> None:
    d = ai_layer_descriptor()
    assert d["ai_layer_contract_version"] == AI_LAYER_CONTRACT_VERSION
    assert d["prompt_registry_keys"] == len(PromptRegistryKey)


def test_default_rate_limits_positive() -> None:
    assert DEFAULT_RATE_LIMIT_POLICY.requests_per_minute_per_user > 0
