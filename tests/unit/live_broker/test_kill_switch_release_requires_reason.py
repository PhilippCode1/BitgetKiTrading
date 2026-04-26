from __future__ import annotations

import pytest
from pydantic import ValidationError

from live_broker.orders.models import KillSwitchRequest


def test_kill_switch_release_requires_reason() -> None:
    with pytest.raises(ValidationError):
        KillSwitchRequest(scope="service", source="operator", reason=" ")
