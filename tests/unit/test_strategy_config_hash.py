from __future__ import annotations

from shared_py.strategy_config_hash import compute_configuration_hash


def test_configuration_hash_deterministic() -> None:
    a = compute_configuration_hash({"x": 1}, {}, {"lev": 2.0})
    b = compute_configuration_hash({"x": 1}, {}, {"lev": 2.0})
    assert a == b
    assert len(a) == 64
