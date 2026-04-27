from __future__ import annotations

from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.eventbus import STREAM_SYSTEM_ALERT, EventEnvelope


def test_system_alert_stream_mapping() -> None:
    env = EventEnvelope(
        event_type="system_alert",
        payload={"severity": "warn", "title": "t", "message": "m"},
    )
    assert env.default_stream() == STREAM_SYSTEM_ALERT


def test_event_envelope_uses_instrument_for_symbol_and_canonical_id() -> None:
    instrument = BitgetInstrumentIdentity(
        market_family="futures",
        symbol="BTCUSDT",
        product_type="USDT-FUTURES",
        margin_account_mode="isolated",
        public_ws_inst_type="USDT-FUTURES",
        private_ws_inst_type="USDT-FUTURES",
        metadata_source="test",
        metadata_verified=True,
        inventory_visible=True,
        analytics_eligible=True,
        paper_shadow_eligible=True,
        live_execution_enabled=True,
        supports_funding=True,
        supports_open_interest=True,
        supports_shorting=True,
        supports_reduce_only=True,
        supports_leverage=True,
    )
    env = EventEnvelope(
        event_type="system_alert",
        instrument=instrument,
        payload={"severity": "warn", "title": "t", "message": "m"},
    )
    assert env.symbol == "BTCUSDT"
    assert env.canonical_instrument_id() == "bitget:futures:USDT-FUTURES:BTCUSDT"
