from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from live_broker.execution.models import OperatorReleasePostBody


def test_operator_release_post_body_default() -> None:
    b = OperatorReleasePostBody()
    assert b.source == "internal-api"
    assert b.audit == {}


def test_operator_release_audit_size_cap() -> None:
    with pytest.raises(ValueError):
        OperatorReleasePostBody(audit={str(i): i for i in range(50)})
