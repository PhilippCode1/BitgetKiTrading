"""Versionierte Prompts aus shared/prompts (Manifest + Task-Dateien)."""

from llm_orchestrator.prompt_governance.manifest import (
    PromptManifest,
    load_prompt_manifest,
)
from llm_orchestrator.prompt_governance.templates import (
    build_ai_strategy_proposal_draft_user_prompt,
    build_assistant_turn_user_prompt,
    build_operator_explain_user_prompt,
    build_safety_incident_diagnosis_user_prompt,
    build_strategy_signal_explain_user_prompt,
)

__all__ = [
    "PromptManifest",
    "load_prompt_manifest",
    "build_ai_strategy_proposal_draft_user_prompt",
    "build_assistant_turn_user_prompt",
    "build_operator_explain_user_prompt",
    "build_safety_incident_diagnosis_user_prompt",
    "build_strategy_signal_explain_user_prompt",
]
