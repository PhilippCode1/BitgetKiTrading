from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.model_registry_scope import normalize_registry_scope


def test_normalize_global() -> None:
    assert normalize_registry_scope(scope_type="global", scope_key="") == ("global", "")
    assert normalize_registry_scope(scope_type="GLOBAL", scope_key="  ") == ("global", "")


def test_normalize_family_lowercase_key() -> None:
    assert normalize_registry_scope(scope_type="market_family", scope_key="Futures") == (
        "market_family",
        "futures",
    )


def test_normalize_cluster_lowercase_key() -> None:
    assert normalize_registry_scope(scope_type="market_cluster", scope_key="Futures::Trend") == (
        "market_cluster",
        "futures::trend",
    )


def test_normalize_symbol_uppercase_key() -> None:
    assert normalize_registry_scope(scope_type="symbol", scope_key="btcusdt") == ("symbol", "BTCUSDT")


def test_normalize_requires_key_for_non_global() -> None:
    with pytest.raises(ValueError, match="scope_key"):
        normalize_registry_scope(scope_type="playbook", scope_key="")
