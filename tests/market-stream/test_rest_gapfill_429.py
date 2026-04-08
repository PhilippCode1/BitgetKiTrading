from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from market_stream.gapfill.rest_gapfill import BitgetRestGapFillWorker
from market_stream.sinks.postgres_raw import PostgresRawSink
from market_stream.sinks.redis_stream import RedisStreamSink


def _minimal_settings() -> MagicMock:
    s = MagicMock()
    s.effective_rest_base_url = "https://api.bitget.com"
    s.symbol = "ETHUSDT"
    s.bitget_demo_enabled = False
    s.rest_product_type_param = "USDT-FUTURES"
    return s


class RestGapfill429Tests(unittest.IsolatedAsyncioTestCase):
    async def test_request_json_retries_429_then_ok(self) -> None:
        redis_sink = MagicMock(spec=RedisStreamSink)
        pg_sink = MagicMock(spec=PostgresRawSink)
        worker = BitgetRestGapFillWorker(
            bitget_settings=_minimal_settings(),
            redis_sink=redis_sink,
            postgres_sink=pg_sink,
            max_429_retries=2,
        )

        req = httpx.Request("GET", "https://api.bitget.com/api/v2/mix/market/candles")
        ok = httpx.Response(
            200,
            request=req,
            json={"code": "00000", "data": [{"k": 1}]},
        )
        r429 = httpx.Response(429, request=req, headers={"Retry-After": "0"})

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=[r429, ok])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("market_stream.gapfill.rest_gapfill.httpx.AsyncClient", return_value=mock_client):
            payload = await worker._request_json(path="/api/v2/mix/market/candles", params={"symbol": "ETHUSDT"})

        self.assertEqual(payload.get("code"), "00000")
        self.assertEqual(mock_client.get.await_count, 2)


if __name__ == "__main__":
    unittest.main()
