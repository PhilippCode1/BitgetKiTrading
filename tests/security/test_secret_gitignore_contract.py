from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read_gitignore() -> str:
    return (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_gitignore_covers_runtime_env_files() -> None:
    text = _read_gitignore()
    assert ".env" in text
    assert ".env.*" in text


def test_gitignore_allows_env_examples() -> None:
    text = _read_gitignore()
    for token in (
        "!.env.local.example",
        "!.env.shadow.example",
        "!.env.production.example",
        "!.env.test.example",
    ):
        assert token in text


def test_owner_release_file_ignored() -> None:
    text = _read_gitignore()
    assert "reports/owner_private_live_release.json" in text
