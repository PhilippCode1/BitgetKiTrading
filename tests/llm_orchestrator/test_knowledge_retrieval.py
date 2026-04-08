from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def knowledge_dir() -> Path:
    return REPO / "docs" / "llm_knowledge"


def test_retrieve_respects_tag_allowlist(knowledge_dir: Path) -> None:
    from llm_orchestrator.knowledge.retrieval import KnowledgeRetriever

    if not (knowledge_dir / "manifest.json").is_file():
        pytest.skip("manifest missing")
    kr = KnowledgeRetriever(knowledge_dir=knowledge_dir, max_chunks=4, max_excerpt_chars=800)
    chunks = kr.retrieve("analyst_hypotheses", "futures funding margin bitget")
    assert len(chunks) >= 1
    assert all(len(c.content_sha256) == 64 for c in chunks)


def test_path_traversal_rejected(knowledge_dir: Path, tmp_path: Path) -> None:
    from llm_orchestrator.knowledge.retrieval import KnowledgeRetriever

    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text(
        '{"version":"1","chunks":[{"id":"x","path":"../secrets.txt","tags":["playbook"],"keywords":[]}]}',
        encoding="utf-8",
    )
    (tmp_path / "secrets.txt").write_text("secret", encoding="utf-8")
    kr = KnowledgeRetriever(knowledge_dir=tmp_path, max_chunks=2, max_excerpt_chars=100)
    assert kr.retrieve("analyst_hypotheses", "playbook") == []
