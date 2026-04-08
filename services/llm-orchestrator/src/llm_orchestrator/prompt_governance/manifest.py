from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from llm_orchestrator.paths import prompts_dir

GuardrailTier = Literal["full", "light", "none"]
TaskStatus = Literal["active", "planned"]


@dataclass(frozen=True)
class TaskPromptSpec:
    task_id: str
    prompt_version: str
    schema_filename: str | None
    instruction_file: str | None
    guardrail_tier: GuardrailTier
    status: TaskStatus
    note_de: str | None


@dataclass(frozen=True)
class PromptManifest:
    manifest_version: str
    guardrails_version: str
    tasks: dict[str, TaskPromptSpec]
    global_system_instruction_de: str
    global_system_prompt_version: str

    def task(self, task_id: str) -> TaskPromptSpec | None:
        return self.tasks.get(task_id)


def _parse_task(task_id: str, raw: dict[str, Any]) -> TaskPromptSpec:
    tier = str(raw.get("guardrail_tier") or "none")
    if tier not in ("full", "light", "none"):
        tier = "none"
    st = str(raw.get("status") or "planned")
    if st not in ("active", "planned"):
        st = "planned"
    note = raw.get("note_de")
    return TaskPromptSpec(
        task_id=task_id,
        prompt_version=str(raw.get("prompt_version") or ""),
        schema_filename=raw.get("schema_filename"),
        instruction_file=raw.get("instruction_file"),
        guardrail_tier=tier,  # type: ignore[arg-type]
        status=st,  # type: ignore[arg-type]
        note_de=str(note) if note is not None else None,
    )


@lru_cache(maxsize=2)
def load_prompt_manifest(path: str | None = None) -> PromptManifest:
    p = Path(path) if path else (prompts_dir() / "prompt_manifest.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    tasks_raw = data.get("tasks") or {}
    tasks: dict[str, TaskPromptSpec] = {}
    for tid, tr in tasks_raw.items():
        if isinstance(tr, dict):
            tasks[str(tid)] = _parse_task(str(tid), tr)
    gtxt, gver = _read_global_system_from_manifest_data(data)
    return PromptManifest(
        manifest_version=str(data.get("manifest_version") or ""),
        guardrails_version=str(data.get("guardrails_version") or ""),
        tasks=tasks,
        global_system_instruction_de=gtxt,
        global_system_prompt_version=gver,
    )


def _read_global_system_from_manifest_data(data: dict[str, Any]) -> tuple[str, str]:
    raw = data.get("global_system")
    if not isinstance(raw, dict):
        return "", ""
    ver = str(raw.get("version") or "").strip()
    rel = raw.get("instruction_file")
    if not isinstance(rel, str) or not rel.strip():
        return "", ver
    base = prompts_dir()
    fp = (base / rel.strip()).resolve()
    if not str(fp).startswith(str(base.resolve())):
        raise ValueError("global_system instruction path outside shared/prompts")
    if not fp.is_file():
        raise ValueError(f"global_system instruction missing: {rel}")
    return fp.read_text(encoding="utf-8").strip(), ver


def read_instruction_text(spec: TaskPromptSpec) -> str:
    if not spec.instruction_file:
        return ""
    base = prompts_dir()
    fp = (base / spec.instruction_file).resolve()
    if not str(fp).startswith(str(base.resolve())):
        raise ValueError("instruction path outside shared/prompts")
    return fp.read_text(encoding="utf-8").strip()
