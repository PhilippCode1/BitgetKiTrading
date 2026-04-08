"""Zahlungsabstraktion: Provider, Checkout, Webhooks (siehe docs/payment_architecture.md)."""

from __future__ import annotations

from typing import Any

from api_gateway.payments.capabilities import build_payment_capabilities

__all__ = [
    "apply_successful_deposit",
    "build_payment_capabilities",
    "process_stripe_webhook_payload",
    "start_deposit_checkout",
]


def __getattr__(name: str) -> Any:
    if name in (
        "apply_successful_deposit",
        "process_stripe_webhook_payload",
        "start_deposit_checkout",
    ):
        from api_gateway.payments import deposit as _deposit

        return getattr(_deposit, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
