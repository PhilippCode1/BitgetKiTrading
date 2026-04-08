"""Live-Mock: Contract-Umschlaege und Replay-Determinismus ohne Netz."""

from __future__ import annotations

import uuid

import pytest

from shared_py.replay_determinism import (
    REPLAY_DETERMINISM_PROTOCOL_VERSION,
    stable_replay_session_id,
)
from tests.integration.doubles.bitget_rest_contract import (
    SAMPLE_DUPLICATE_CLIENT_OID,
    SAMPLE_PLACE_ORDER_OK,
    SAMPLE_PUBLIC_TIME_OK,
    SAMPLE_SIGNATURE_ERROR,
    assert_bitget_envelope_shape,
)


@pytest.mark.live_mock
def test_bitget_contract_samples_have_envelope_fields() -> None:
    for sample in (
        SAMPLE_PUBLIC_TIME_OK,
        SAMPLE_PLACE_ORDER_OK,
        SAMPLE_SIGNATURE_ERROR,
        SAMPLE_DUPLICATE_CLIENT_OID,
    ):
        assert_bitget_envelope_shape(sample)


@pytest.mark.live_mock
def test_bitget_success_codes_are_string_00000_where_applicable() -> None:
    assert SAMPLE_PUBLIC_TIME_OK["code"] == "00000"
    assert SAMPLE_PLACE_ORDER_OK["code"] == "00000"
    assert str(SAMPLE_SIGNATURE_ERROR["code"]) == "40009"


@pytest.mark.live_mock
def test_stable_replay_session_id_is_reproducible() -> None:
    a = stable_replay_session_id(
        symbol="BTCUSDT",
        timeframes=["5m", "1m"],
        from_ts_ms=1,
        to_ts_ms=2,
        speed_factor=1.0,
        dedupe_prefix="t",
        publish_ticks=False,
    )
    b = stable_replay_session_id(
        symbol="btcusdt",
        timeframes=["1m", "5m"],
        from_ts_ms=1,
        to_ts_ms=2,
        speed_factor=1.0,
        dedupe_prefix="t",
        publish_ticks=False,
    )
    assert a == b
    assert isinstance(a, uuid.UUID)
    assert REPLAY_DETERMINISM_PROTOCOL_VERSION
