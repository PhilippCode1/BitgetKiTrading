"""
Self-Healing Code-Fix-Agent: Forensic-Kontext, Code-Suche, LLM-Diagnose, Sandbox-Tests, Telegram-Vorschlag.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from pathlib import Path
from typing import Any

import httpx
from redis import Redis
from shared_py.eventbus import RedisStreamBus
from shared_py.eventbus.envelope import STREAM_OPERATOR_INTEL, EventEnvelope
from shared_py.observability.execution_forensic import redact_nested_mapping

from learning_engine.config import LearningEngineSettings
from learning_engine.self_healing.protocol import (
    ForensicBundle,
    RepairLLMOutput,
    SelfHealingProposal,
)
from learning_engine.self_healing.recursion_guard import (
    reserve_alert_processing,
    should_skip_for_recursion,
)
from learning_engine.self_healing.sandbox_runner import run_tests_in_sandbox

logger = logging.getLogger("learning_engine.self_healing.agent")

REPAIR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypothesis_de": {"type": "string", "minLength": 3, "maxLength": 8000},
        "root_cause_tags": {
            "type": "array",
            "maxItems": 24,
            "items": {"type": "string", "maxLength": 128},
        },
        "proposed_unified_diff": {"type": "string", "minLength": 1, "maxLength": 120000},
        "recommended_verify_command_de": {"type": "string", "maxLength": 2000},
        "confidence_0_1": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["hypothesis_de", "proposed_unified_diff", "confidence_0_1"],
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _instruction_text(repo: Path) -> str:
    p = repo / "shared" / "prompts" / "tasks" / "safety_incident_diagnosis.instruction_de.txt"
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return "Diagnostiziere den Fehler knapp auf Deutsch (keine Secrets)."


def _extract_stacktrace(payload: dict[str, Any]) -> str:
    d = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    for k in ("stacktrace", "traceback", "tb", "error", "exception"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:24_000]
    msg = str(payload.get("message") or "")
    if "Traceback" in msg:
        return msg[:24_000]
    return ""


def _paths_from_stack(stack: str, repo: Path) -> list[str]:
    found: list[str] = []
    for m in re.finditer(r'File "([^"]+)"', stack):
        p = Path(m.group(1))
        try:
            rel = p.resolve().relative_to(repo.resolve())
            found.append(str(rel).replace("\\", "/"))
        except Exception:
            if m.group(1).startswith("services/") or m.group(1).startswith("shared/"):
                found.append(m.group(1).replace("\\", "/"))
    return list(dict.fromkeys(found))[:12]


def _read_snippets(repo: Path, rel_paths: list[str], *, max_chars: int = 24_000) -> str:
    chunks: list[str] = []
    n = 0
    for rel in rel_paths:
        if n >= max_chars:
            break
        fp = (repo / rel).resolve()
        if not str(fp).startswith(str(repo.resolve())):
            continue
        if not fp.is_file():
            continue
        try:
            txt = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        head = txt[:8000]
        chunks.append(f"--- {rel} ---\n{head}\n")
        n += len(head)
    return "\n".join(chunks)[:max_chars]


def _optional_audit_ledger_context(settings: LearningEngineSettings) -> list[dict[str, Any]]:
    base = (settings.audit_ledger_base_url or "").strip().rstrip("/")
    if not base or not (settings.service_internal_api_key or "").strip():
        return []
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(
                f"{base}/internal/v1/verify-chain",
                headers={
                    "X-Internal-Service-Key": settings.service_internal_api_key.strip()
                },
            )
        if r.status_code != 200:
            return [{"audit_ledger_verify_http": r.status_code}]
        return [r.json()]
    except Exception as exc:
        return [{"audit_ledger_error": str(exc)[:400]}]


def _call_llm_repair_plan(
    settings: LearningEngineSettings,
    diagnostic_prompt: str,
) -> RepairLLMOutput | None:
    base = (settings.llm_orchestrator_base_url or "").strip().rstrip("/")
    key = (settings.service_internal_api_key or "").strip()
    if not base or not key:
        return None
    url = f"{base}/llm/structured"
    body: dict[str, Any] = {
        "prompt": diagnostic_prompt,
        "schema_json": REPAIR_OUTPUT_SCHEMA,
        "temperature": 0.1,
    }
    try:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(
                url,
                json=body,
                headers={"X-Internal-Service-Key": key},
            )
        if r.status_code != 200:
            logger.warning("llm structured self_healing status=%s %s", r.status_code, r.text[:500])
            return None
        data = r.json()
        inner = data.get("result") if isinstance(data.get("result"), dict) else data
        return RepairLLMOutput.model_validate(inner)
    except Exception as exc:
        logger.exception("llm self_healing call failed: %s", exc)
        return None


def _publish_operator_proposal(
    settings: LearningEngineSettings,
    proposal: SelfHealingProposal,
    *,
    title_de: str,
) -> None:
    bus = RedisStreamBus.from_url(
        settings.redis_url,
        dedupe_ttl_sec=0,
        default_block_ms=settings.eventbus_block_ms,
        default_count=settings.eventbus_count,
    )
    text = (
        f"{title_de}\n\n"
        f"Hypothese:\n{proposal.hypothesis_de[:3500]}\n\n"
        f"Betroffene Pfade: {', '.join(proposal.affected_paths) or '—'}\n"
        f"Sandbox: {proposal.sandbox.command_de if proposal.sandbox else '—'} "
        f"(exit={proposal.sandbox.exit_code if proposal.sandbox else 'n/a'})\n\n"
        f"[APPLY FIX] proposal_id={proposal.proposal_id} token={proposal.apply_token}\n"
        f"(Nur nach manueller Pruefung; Anwendung ueber learning-engine POST "
        f"/internal/self-healing/apply mit internem Service-Key.)\n"
    )
    env = EventEnvelope(
        event_type="operator_intel",
        symbol="SYSTEM",
        dedupe_key=f"self_healing:{proposal.proposal_id}",
        payload={
            "intel_kind": "self_healing_proposal",
            "severity": "warn",
            "title_de": title_de,
            "text": text,
            "proposal": proposal.model_dump(),
            "self_healing_origin": "self_healing_pipeline",
        },
        trace={"source": "learning-engine-self-healing"},
    )
    bus.publish(STREAM_OPERATOR_INTEL, env)


def _store_apply_token(redis_url: str, proposal_id: str, token: str, patch: str) -> None:
    r = Redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
    try:
        r.setex(f"self_healing:apply:{proposal_id}", 7200, token)
        r.setex(f"self_healing:patch:{proposal_id}", 7200, patch[:200_000])
    finally:
        r.close()


def run_self_healing_for_system_alert(
    settings: LearningEngineSettings,
    env: EventEnvelope,
) -> SelfHealingProposal:
    """Synchroner Einstieg aus dem Redis-Consumer."""
    if env.event_type != "system_alert":
        return SelfHealingProposal(
            proposal_id="na",
            status="skipped_no_trigger",
            hypothesis_de="Kein system_alert",
        )
    payload = dict(env.payload or {})
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    if should_skip_for_recursion(details):
        return SelfHealingProposal(
            proposal_id="skip",
            status="skipped_recursion",
            hypothesis_de="Rekursionsschutz (Folge-Event Self-Healing)",
        )

    ak = str(payload.get("alert_key") or env.dedupe_key or "")
    sev = str(payload.get("severity") or "").lower()
    trigger = ak == "CRITICAL_RUNTIME_EXCEPTION" or (
        settings.self_healing_trigger_svc_critical
        and ak.startswith("svc:")
        and sev == "critical"
    )
    if not trigger:
        return SelfHealingProposal(
            proposal_id="skip",
            status="skipped_no_trigger",
            hypothesis_de="Kein Self-Healing-Trigger",
        )

    dk = str(payload.get("dedupe_key") or env.dedupe_key or ak or "")
    if not reserve_alert_processing(settings.redis_url, dk or None):
        return SelfHealingProposal(
            proposal_id="deduped",
            status="skipped_recursion",
            hypothesis_de="Bereits reserviert / Dedupe",
        )

    repo = _repo_root()
    stack = _extract_stacktrace(payload)
    rels = _paths_from_stack(stack, repo) if stack else []
    snippets = _read_snippets(repo, rels) if rels else ""
    audit_tail = _optional_audit_ledger_context(settings)

    fb = ForensicBundle(
        alert_key=ak or None,
        severity=sev or None,
        title=str(payload.get("title") or "")[:500] or None,
        message=str(payload.get("message") or "")[:4000] or None,
        details=redact_nested_mapping(details, max_depth=3),
        stacktrace_excerpt=stack[:12_000] if stack else None,
        audit_ledger_tail_json=audit_tail or None,
    )

    instruction = _instruction_text(repo)
    diagnostic = (
        f"{instruction}\n\n---\nDIAGNOSTIC_KONTEXT (JSON):\n"
        f"{json.dumps(fb.model_dump(), ensure_ascii=False)[:28_000]}\n\n"
        f"---\nCODE_SNIPPETS (Repo, gekuerzt):\n{snippets or '(keine Pfade aus Stacktrace)'}\n\n"
        "---\nFRAGE:\n"
        "Erzeuge einen minimalen unified-diff Patch, der die wahrscheinlichste Ursache behebt. "
        "Keine Secrets. Wenn unsicher: kleiner Patch mit Kommentar.\n"
        "Hinweis: Du fuehrst keine Live-Aenderungen aus; nur Vorschlag gemaess safety_incident Diagnose.\n"
    )

    llm_out = _call_llm_repair_plan(settings, diagnostic)
    proposal_id = str(uuid.uuid4())
    apply_token = secrets.token_urlsafe(18)
    if llm_out is None:
        prop = SelfHealingProposal(
            proposal_id=proposal_id,
            status="skipped_no_llm",
            hypothesis_de="LLM-Orchestrator nicht erreichbar oder nicht konfiguriert.",
            apply_token="",
        )
        return prop

    sandbox = run_tests_in_sandbox(repo, timeout_sec=float(settings.self_healing_sandbox_timeout_sec))
    ok = sandbox.exit_code == 0
    prop = SelfHealingProposal(
        proposal_id=proposal_id,
        status="tests_passed" if ok else "tests_failed",
        hypothesis_de=llm_out.hypothesis_de,
        proposed_unified_diff=llm_out.proposed_unified_diff,
        apply_token=apply_token if ok else "",
        sandbox=sandbox,
        affected_paths=rels,
    )
    if ok:
        _store_apply_token(settings.redis_url, proposal_id, apply_token, llm_out.proposed_unified_diff)
        _publish_operator_proposal(
            settings,
            prop,
            title_de="Self-Healing Proposal (Tests OK)",
        )
    else:
        _publish_operator_proposal(
            settings,
            prop,
            title_de="Self-Healing Entwurf (Tests fehlgeschlagen — kein APPLY)",
        )
    return prop
