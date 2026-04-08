from __future__ import annotations

import time
import unittest

from market_stream.bitget_ws.rate_limiter import RateLimiter


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_burst_then_waits(self) -> None:
        limiter = RateLimiter(10)
        start = time.monotonic()
        for _ in range(11):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.08)


if __name__ == "__main__":
    unittest.main()
