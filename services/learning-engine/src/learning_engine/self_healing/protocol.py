"""Pydantic-Modelle fuer Self-Healing / Repair-Protokoll."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ForensicBundle(BaseModel):
    """Redaktierter Forensic-Kontext (keine Secrets)."""

    alert_key: str | None = None
    severity: str | None = None
    title: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    stacktrace_excerpt: str | None = None
    audit_ledger_tail_json: list[dict[str, Any]] | None = None


class RepairLLMOutput(BaseModel):
    """Strukturierte LLM-Antwort (json_schema via Orchestrator)."""

    hypothesis_de: str = Field(..., min_length=3, max_length=8000)
    root_cause_tags: list[str] = Field(default_factory=list)
    proposed_unified_diff: str = Field(..., min_length=1, max_length=120_000)
    recommended_verify_command_de: str = Field(default="", max_length=2000)
    confidence_0_1: float = Field(ge=0.0, le=1.0)

    @field_validator("root_cause_tags")
    @classmethod
    def _cap_tags(cls, v: list[str]) -> list[str]:
        return [str(x).strip() for x in v[:24] if str(x).strip()]


class SandboxTestResult(BaseModel):
    exit_code: int
    stdout_tail: str = Field(..., max_length=24_000)
    stderr_tail: str = Field(default="", max_length=24_000)
    command_de: str = Field(default="", max_length=2000)


class SelfHealingProposal(BaseModel):
    """Payload fuer operator_intel / Telegram."""

    proposal_id: str = Field(..., min_length=2, max_length=64)
    status: Literal[
        "tests_passed",
        "tests_failed",
        "skipped_no_llm",
        "skipped_recursion",
        "skipped_no_trigger",
    ]
    hypothesis_de: str = ""
    proposed_unified_diff: str = ""
    apply_token: str = Field(default="", max_length=128)
    sandbox: SandboxTestResult | None = None
    affected_paths: list[str] = Field(default_factory=list)
