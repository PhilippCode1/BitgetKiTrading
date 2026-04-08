from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for p in (REPO_ROOT, LIVE_BROKER_SRC):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from live_broker.control_plane.capabilities import (
    CONTROL_PLANE_MATRIX_VERSION,
    assert_read_capability,
    assert_write_capability,
    capability_matrix_for_profile,
)
from live_broker.private_rest import BitgetRestError
from shared_py.bitget.instruments import endpoint_profile_for


def test_matrix_version_constant() -> None:
    assert CONTROL_PLANE_MATRIX_VERSION == "bitget-control-plane-v1"


def test_futures_supported_writes_and_reads() -> None:
    profile = endpoint_profile_for("futures")
    m = {row["category"]: row for row in capability_matrix_for_profile(profile)}
    assert m["order_create"]["status"] == "supported"
    assert m["order_replace"]["status"] == "supported"
    assert m["cancel_all"]["status"] == "supported"
    assert m["reduce_only"]["status"] == "supported"
    assert m["leverage_config"]["status"] == "supported"
    assert m["order_history"]["status"] == "supported"
    assert m["fills"]["status"] == "supported"
    assert_read_capability(profile, "order_history")
    assert_write_capability(profile, "order_create")


def test_spot_cancel_all_and_reduce_only_disabled_explicitly() -> None:
    profile = endpoint_profile_for("spot")
    m = {row["category"]: row for row in capability_matrix_for_profile(profile)}
    assert m["cancel_all"]["execution_disabled"] is True
    assert m["reduce_only"]["execution_disabled"] is True
    assert m["order_history"]["status"] == "supported"
    with pytest.raises(BitgetRestError) as exc:
        assert_write_capability(profile, "cancel_all")
    assert exc.value.classification == "service_disabled"
    assert "cancel_all" in str(exc.value)


def test_margin_isolated_fill_history_disabled_without_path() -> None:
    profile = endpoint_profile_for("margin", margin_account_mode="isolated")
    m = {row["category"]: row for row in capability_matrix_for_profile(profile)}
    assert m["fills"]["execution_disabled"] is True
    with pytest.raises(BitgetRestError):
        assert_read_capability(profile, "fills")


def test_assert_write_rejects_read_category() -> None:
    with pytest.raises(ValueError):
        assert_write_capability(endpoint_profile_for("futures"), "order_history")  # type: ignore[arg-type]
