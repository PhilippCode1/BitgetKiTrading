from __future__ import annotations

from llm_orchestrator.paths import find_repo_root, schemas_dir
from llm_orchestrator.prompt_governance.manifest import (
    load_prompt_manifest,
    read_instruction_text,
)


def test_prompt_manifest_matches_instruction_files() -> None:
    load_prompt_manifest.cache_clear()
    m = load_prompt_manifest()
    assert m.manifest_version
    assert m.guardrails_version
    for _tid, spec in m.tasks.items():
        if spec.status == "active" and spec.instruction_file:
            txt = read_instruction_text(spec)
            assert len(txt) > 40
        if spec.schema_filename:
            p = schemas_dir() / spec.schema_filename
            assert p.is_file(), spec.schema_filename


def test_eval_baseline_file_exists() -> None:
    p = find_repo_root() / "shared" / "prompts" / "eval_baseline.json"
    assert p.is_file()
