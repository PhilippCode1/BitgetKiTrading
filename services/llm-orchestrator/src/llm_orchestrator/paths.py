from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for d in here.parents:
        if (d / "shared" / "contracts" / "schemas").is_dir():
            return d
    raise FileNotFoundError("Repo-Root mit shared/contracts/schemas nicht gefunden")


def schemas_dir() -> Path:
    return find_repo_root() / "shared" / "contracts" / "schemas"


def news_summary_schema_path() -> Path:
    return schemas_dir() / "news_summary.schema.json"


def llm_knowledge_dir() -> Path:
    return find_repo_root() / "docs" / "llm_knowledge"


def prompts_dir() -> Path:
    return find_repo_root() / "shared" / "prompts"


def load_json_schema(filename: str) -> dict[str, Any]:
    p = schemas_dir() / filename
    return json.loads(p.read_text(encoding="utf-8"))


def agent_communication_schema_path() -> Path:
    return schemas_dir() / "agent_communication.schema.json"
