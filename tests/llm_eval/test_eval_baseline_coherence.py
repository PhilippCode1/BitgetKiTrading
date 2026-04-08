from __future__ import annotations

import json

from fastapi.testclient import TestClient

from llm_orchestrator.paths import find_repo_root, prompts_dir
from llm_orchestrator.prompt_governance.manifest import load_prompt_manifest


def test_eval_baseline_file_valid() -> None:
    p = find_repo_root() / "shared" / "prompts" / "eval_baseline.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("release_gate") is True
    cases = data.get("cases")
    assert isinstance(cases, list) and len(cases) >= 9
    categories = {str(c.get("category")) for c in cases if isinstance(c, dict)}
    assert "operator" in categories
    assert "customer_help" in categories
    assert "billing" in categories
    assert "chart_intelligence" in categories
    assert "provider" in categories
    assert "safety_ai" in categories


def test_eval_baseline_task_types_exist_in_manifest() -> None:
    load_prompt_manifest.cache_clear()
    m = load_prompt_manifest()
    p = prompts_dir() / "eval_baseline.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    active = {tid for tid, sp in m.tasks.items() if sp.status == "active"}
    for c in data.get("cases") or []:
        if not isinstance(c, dict):
            continue
        for tt in c.get("task_types") or []:
            tid = str(tt).strip()
            if not tid:
                continue
            assert tid in m.tasks, f"unknown task_type in baseline: {tid}"
            if tid in active:
                assert m.tasks[tid].status == "active"


def test_governance_summary_includes_eval_and_system(client: TestClient) -> None:
    r = client.get("/llm/governance/summary")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    sp = data.get("system_prompt")
    assert isinstance(sp, dict)
    assert sp.get("global_version")
    assert isinstance(sp.get("global_instruction_chars"), int)
    er = data.get("eval_regression")
    assert isinstance(er, dict)
    assert er.get("release_gate") is True
    assert er.get("case_count", 0) >= 9
    cases = er.get("cases")
    assert isinstance(cases, list)
    assert any(x.get("id") == "operator_explain_smoke" for x in cases if isinstance(x, dict))
