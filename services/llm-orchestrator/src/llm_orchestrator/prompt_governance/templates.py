from __future__ import annotations

from llm_orchestrator.agents.tsfm_semantics import (
    OPERATOR_MARKET_DATA_GAP_DIRECTIVE_DE,
)
from llm_orchestrator.prompt_governance.manifest import (
    load_prompt_manifest,
    read_instruction_text,
)


def build_operator_explain_user_prompt(
    *,
    question_de: str,
    readonly_context_json_text: str,
    retrieval_block: str,
) -> str:
    m = load_prompt_manifest()
    spec = m.task("operator_explain")
    if not spec or spec.status != "active":
        raise RuntimeError("operator_explain nicht aktiv im Prompt-Manifest")
    instr = read_instruction_text(spec)
    return (
        f"{instr}\n\n"
        f"DATENLUEKEN-REGEL:\n{OPERATOR_MARKET_DATA_GAP_DIRECTIVE_DE}\n\n"
        f"RETRIEVAL:\n{retrieval_block}\n\n"
        f"FRAGE:\n{question_de}\n\n"
        f"READONLY_KONTEXT (pro Symbol: News/Orderbook/Signale/Chart, evtl. Platzhalter "
        f"wenn leer):\n{readonly_context_json_text}"
    )


def build_assistant_turn_user_prompt(
    *,
    task_type: str,
    assist_role: str,
    history_messages: list[dict[str, str]],
    user_message_de: str,
    server_context_json_text: str,
    retrieval_block: str,
) -> str:
    m = load_prompt_manifest()
    spec = m.task(task_type)
    if not spec or spec.status != "active":
        raise RuntimeError(f"{task_type} nicht aktiv im Prompt-Manifest")
    instr = read_instruction_text(spec)
    lines: list[str] = []
    if history_messages:
        lines.append("VERLAUF (nur Erklaerungsdialog, keine Orderhoheit):")
        for msg in history_messages:
            r = msg.get("role") or ""
            c = (msg.get("content_de") or "").strip()
            if not c:
                continue
            label = "NUTZER" if r == "user" else "ASSISTENT"
            lines.append(f"[{label}] {c}")
        lines.append("")
    lines.append(f"AKTUELLE_NUTZER_NACHRICHT (Rolle={assist_role}):")
    lines.append(user_message_de.strip())
    hist_block = "\n".join(lines)
    return (
        f"{instr}\n\n"
        f"RETRIEVAL:\n{retrieval_block}\n\n"
        f"{hist_block}\n\n"
        f"SERVER_KONTEXT_JSON:\n{server_context_json_text}"
    )


def build_ai_strategy_proposal_draft_user_prompt(
    *,
    chart_context_json_text: str,
    focus_question_de: str,
    retrieval_block: str,
) -> str:
    m = load_prompt_manifest()
    spec = m.task("ai_strategy_proposal_draft")
    if not spec or spec.status != "active":
        raise RuntimeError("ai_strategy_proposal_draft nicht aktiv im Prompt-Manifest")
    instr = read_instruction_text(spec)
    fq = focus_question_de.strip()
    focus_block = f"OPERATOR_FOKUSFRAGE:\n{fq}\n\n" if fq else ""
    return (
        f"{instr}\n\n"
        f"RETRIEVAL:\n{retrieval_block}\n\n"
        f"{focus_block}"
        f"CHART_UND_SIGNAL_KONTEXT_JSON:\n{chart_context_json_text}"
    )


def build_strategy_signal_explain_user_prompt(
    *,
    signal_context_json_text: str,
    focus_question_de: str,
    retrieval_block: str,
) -> str:
    m = load_prompt_manifest()
    spec = m.task("strategy_signal_explain")
    if not spec or spec.status != "active":
        raise RuntimeError("strategy_signal_explain nicht aktiv im Prompt-Manifest")
    instr = read_instruction_text(spec)
    fq = focus_question_de.strip()
    focus_block = f"OPERATOR_FOKUSFRAGE:\n{fq}\n\n" if fq else ""
    return (
        f"{instr}\n\n"
        f"RETRIEVAL:\n{retrieval_block}\n\n"
        f"{focus_block}"
        f"SIGNAL_SNAPSHOT_JSON:\n{signal_context_json_text}"
    )


def build_safety_incident_diagnosis_user_prompt(
    *,
    question_de: str,
    diagnostic_context_json_text: str,
    retrieval_block: str,
) -> str:
    m = load_prompt_manifest()
    spec = m.task("safety_incident_diagnosis")
    if not spec or spec.status != "active":
        raise RuntimeError("safety_incident_diagnosis nicht aktiv im Prompt-Manifest")
    instr = read_instruction_text(spec)
    return (
        f"{instr}\n\n"
        f"RETRIEVAL:\n{retrieval_block}\n\n"
        f"FRAGE:\n{question_de.strip()}\n\n"
        f"DIAGNOSTIC_KONTEXT_JSON:\n{diagnostic_context_json_text}"
    )
