from __future__ import annotations

from learning_engine.registry.models import (
    requires_promotion_manual_override,
    transition_allowed,
)


def test_allowed_edges() -> None:
    assert transition_allowed("shadow", "candidate")
    assert transition_allowed("candidate", "promoted")
    assert transition_allowed("promoted", "retired")
    assert transition_allowed("retired", "shadow")


def test_disallowed() -> None:
    assert not transition_allowed("shadow", "promoted")
    assert not transition_allowed("promoted", "candidate")
    assert not transition_allowed("promoted", "promoted")
    assert not transition_allowed("shadow", "shadow")
    assert not transition_allowed(None, "candidate")


def test_promotion_manual_override_flag() -> None:
    assert requires_promotion_manual_override("candidate", "promoted")
    assert not requires_promotion_manual_override("shadow", "candidate")
