from __future__ import annotations

import unittest

from market_stream.normalization.models import (
    NormalizedEvent,
    extract_exchange_ts_ms,
    extract_sequence,
)


class NormalizationTests(unittest.TestCase):
    def test_from_ws_message_normalizes_core_fields(self) -> None:
        message = {
            "action": "snapshot",
            "arg": {
                "instType": "USDT-FUTURES",
                "channel": "ticker",
                "instId": "BTCUSDT",
            },
            "data": [{"ts": "1710000000000", "lastPr": "50000"}],
        }

        event = NormalizedEvent.from_ws_message(message)

        self.assertEqual(event.source, "bitget_ws_public")
        self.assertEqual(event.inst_type, "USDT-FUTURES")
        self.assertEqual(event.channel, "ticker")
        self.assertEqual(event.inst_id, "BTCUSDT")
        self.assertEqual(event.action, "snapshot")
        self.assertEqual(event.exchange_ts_ms, 1710000000000)

    def test_from_gapfill_payload_marks_rest_source(self) -> None:
        payload = {"code": "00000", "data": [["1710000000000", "50000"]]}

        event = NormalizedEvent.from_gapfill_payload(
            inst_type="USDT-FUTURES",
            channel="candles:1m",
            inst_id="BTCUSDT",
            action="snapshot",
            payload=payload,
        )

        self.assertEqual(event.source, "bitget_rest_gapfill")
        self.assertEqual(event.exchange_ts_ms, 1710000000000)

    def test_extract_helpers_handle_sequence(self) -> None:
        payload = {"data": [{"seq": "42", "ts": "1710000000001"}]}

        self.assertEqual(extract_sequence(payload), 42)
        self.assertEqual(extract_exchange_ts_ms(payload), 1710000000001)


if __name__ == "__main__":
    unittest.main()
