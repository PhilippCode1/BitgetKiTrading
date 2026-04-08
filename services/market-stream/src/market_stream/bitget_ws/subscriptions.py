from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Subscription:
    inst_type: str
    channel: str
    inst_id: str

    def to_ws_arg(self) -> dict[str, str]:
        return {
            "instType": self.inst_type,
            "channel": self.channel,
            "instId": self.inst_id,
        }


class SubscriptionLimitExceeded(ValueError):
    """Raised when the connection would exceed Bitget's channel guidance."""


class SubscriptionManager:
    def __init__(self, max_channels: int = 50) -> None:
        if max_channels <= 0:
            raise ValueError("max_channels muss > 0 sein")
        self._max_channels = max_channels
        self._subscriptions: set[Subscription] = set()

    def add(self, subscription: Subscription) -> bool:
        if subscription in self._subscriptions:
            return False
        if len(self._subscriptions) >= self._max_channels:
            raise SubscriptionLimitExceeded(
                f"maximal {self._max_channels} aktive Channels pro Verbindung erlaubt"
            )
        self._subscriptions.add(subscription)
        return True

    def remove(self, subscription: Subscription) -> bool:
        if subscription not in self._subscriptions:
            return False
        self._subscriptions.remove(subscription)
        return True

    def contains(self, subscription: Subscription) -> bool:
        return subscription in self._subscriptions

    def list(self) -> list[Subscription]:
        return sorted(
            self._subscriptions,
            key=lambda item: (item.channel, item.inst_type, item.inst_id),
        )

    def count(self) -> int:
        return len(self._subscriptions)

    def build_subscribe_payload(
        self,
        subscriptions: list[Subscription],
    ) -> dict[str, object]:
        return self._build_payload("subscribe", subscriptions)

    def build_unsubscribe_payload(
        self,
        subscriptions: list[Subscription],
    ) -> dict[str, object]:
        return self._build_payload("unsubscribe", subscriptions)

    @staticmethod
    def _build_payload(
        op: str,
        subscriptions: list[Subscription],
    ) -> dict[str, object]:
        return {"op": op, "args": [item.to_ws_arg() for item in subscriptions]}
