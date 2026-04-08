from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.playbook_registry import (
    PLAYBOOK_REGISTRY,
    PLAYBOOK_REGISTRY_HASH,
    PLAYBOOK_REGISTRY_VERSION,
    get_playbook,
    playbook_registry_descriptor,
)


def test_playbook_registry_descriptor_is_stable() -> None:
    desc = playbook_registry_descriptor()
    assert desc["registry_version"] == PLAYBOOK_REGISTRY_VERSION
    assert desc["registry_hash"] == PLAYBOOK_REGISTRY_HASH
    assert desc["playbook_count"] == len(PLAYBOOK_REGISTRY)


def test_playbook_ids_unique_and_resolvable() -> None:
    ids = [item.playbook_id for item in PLAYBOOK_REGISTRY]
    assert len(ids) == len(set(ids))
    carry = get_playbook("carry_funding_capture")
    assert carry is not None
    assert carry.playbook_family == "carry_funding"
    assert carry.target_market_families == ["futures"]
