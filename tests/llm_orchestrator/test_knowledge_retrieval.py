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


def test_operator_readonly_fills_gaps() -> None:
    from llm_orchestrator.knowledge import retrieval as r

    s = r.format_operator_readonly_pro_symbol(
        {
            "symbol": "BTCUSDT",
            "news": [],
            "orderbook": {"bids": [[1.0, 0.1]]},
        },
    )
    assert "BTCUSDT" in s
    assert r.PLACEHOLDER_NO_NEWS in s
    assert r.PLACEHOLDER_NO_NEWS == "[KEINE AKTUELLEN NEWS VERFÜGBAR]"
    assert "1.0" in s
    assert r.PLACEHOLDER_NO_CHART in s
    assert r.PLACEHOLDER_NO_SIGNALS in s


def test_operator_readonly_exotic_symbol_no_news_succeeds() -> None:
    """Pro-Symbol mit DB-Lage aber ohne News: Platzhalter, kein Abbruch."""
    from llm_orchestrator.knowledge import retrieval as r

    s = r.format_operator_readonly_pro_symbol(
        {
            "symbol": "EXOTICCOINUSDT",
            "news": [],
            "orderbook": None,
        },
    )
    assert "EXOTICCOINUSDT" in s
    assert r.PLACEHOLDER_NO_NEWS in s
    assert "news:" in s
    assert r.PLACEHOLDER_NO_ORDERBOOK in s


def test_operator_readonly_not_dict() -> None:
    from llm_orchestrator.knowledge import retrieval as r

    s = r.format_operator_readonly_pro_symbol(None)  # type: ignore[arg-type]
    assert r.PLACEHOLDER_NO_NEWS in s
    assert "ungueltiger" in s.lower() or "kein json" in s.lower()
