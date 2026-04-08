from __future__ import annotations

import unittest

from market_stream.bitget_ws.subscriptions import (
    Subscription,
    SubscriptionLimitExceeded,
    SubscriptionManager,
)


class SubscriptionManagerTests(unittest.TestCase):
    def test_dedupes_same_subscription(self) -> None:
        manager = SubscriptionManager(max_channels=50)
        subscription = Subscription(
            inst_type="USDT-FUTURES",
            channel="ticker",
            inst_id="BTCUSDT",
        )

        self.assertTrue(manager.add(subscription))
        self.assertFalse(manager.add(subscription))
        self.assertEqual(manager.count(), 1)

    def test_enforces_max_channel_limit(self) -> None:
        manager = SubscriptionManager(max_channels=1)
        manager.add(
            Subscription(
                inst_type="USDT-FUTURES",
                channel="ticker",
                inst_id="BTCUSDT",
            )
        )

        with self.assertRaises(SubscriptionLimitExceeded):
            manager.add(
                Subscription(
                    inst_type="USDT-FUTURES",
                    channel="trade",
                    inst_id="BTCUSDT",
                )
            )


if __name__ == "__main__":
    unittest.main()
