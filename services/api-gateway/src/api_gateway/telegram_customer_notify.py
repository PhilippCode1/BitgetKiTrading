"""Re-Export: Kunden-Telegram-Outbox (Implementierung in shared_py)."""

from __future__ import annotations

from shared_py.customer_telegram_notify import enqueue_customer_notify

__all__ = ["enqueue_customer_notify"]
