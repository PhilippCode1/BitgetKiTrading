from __future__ import annotations

import pytest
from pydantic import ValidationError

from live_broker.orders.models import SafetyLatchReleaseRequest


def test_safety_latch_release_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SafetyLatchReleaseRequest(source="operator", reason=" ", note="")
