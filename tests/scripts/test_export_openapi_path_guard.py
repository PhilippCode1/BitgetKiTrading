"""Regression: export_openapi muss config/ (Repo-Root) importierbar machen (ModuleNotFoundError: config)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "export_openapi.py"


def test_export_openapi_inserts_repo_root_before_config_import() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "sys.path.insert(0, str(root))" in text
    assert "from config.required_secrets import" in text
    i_root = text.index("sys.path.insert(0, str(root))")
    i_cfg = text.index("from config.required_secrets import")
    assert i_root < i_cfg, "Repo-Root muss vor config-Import in sys.path stehen"
