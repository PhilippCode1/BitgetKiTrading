"""Oeffentliche Zahlungsfaehigkeiten (Feature-Flags, keine Secrets)."""

from __future__ import annotations

from typing import Any

from config.gateway_settings import GatewaySettings


def build_payment_capabilities(settings: GatewaySettings) -> dict[str, Any]:
    env = settings.payment_environment()
    master = bool(settings.commercial_enabled and settings.payment_checkout_enabled)

    def method(
        mid: str,
        label_en: str,
        *,
        enabled: bool,
        providers: list[str],
        disabled_reason: str | None = None,
        usage_constraint: str | None = None,
        subscription_recurring_eligible: bool | None = None,
        requires_active_checkout: bool = True,
    ) -> dict[str, Any]:
        eff = (enabled and master) if requires_active_checkout else (enabled and settings.commercial_enabled)
        m: dict[str, Any] = {
            "id": mid,
            "label": label_en,
            "enabled": eff,
            "providers": providers,
        }
        if disabled_reason and not enabled:
            m["disabled_reason"] = disabled_reason
        if usage_constraint:
            m["usage_constraint"] = usage_constraint
        if subscription_recurring_eligible is not None:
            m["subscription_recurring_eligible"] = subscription_recurring_eligible
        return m

    stripe_ok = bool(
        master
        and settings.payment_stripe_enabled
        and settings.payment_stripe_secret_key.strip()
        and (env == "sandbox" or settings.payment_stripe_webhook_secret.strip())
    )
    if env == "live" and settings.payment_stripe_enabled:
        stripe_ok = stripe_ok and bool(settings.payment_stripe_webhook_secret.strip())

    mock_ok = bool(
        master
        and settings.payment_mock_enabled
        and (env == "sandbox" or not settings.production)
        and settings.payment_mock_webhook_secret.strip()
    )

    wise_ingest = bool(
        settings.commercial_enabled
        and settings.payment_wise_webhook_enabled
        and bool(settings.payment_wise_webhook_secret.strip())
    )
    paypal_stub = bool(
        settings.commercial_enabled
        and settings.payment_paypal_stub_webhook_enabled
        and settings.payment_paypal_stub_webhook_secret.strip()
    )

    methods = [
        method(
            "card",
            "Card",
            enabled=stripe_ok or mock_ok,
            providers=[p for p, ok in (("stripe", stripe_ok), ("mock", mock_ok)) if ok],
            disabled_reason=None if (stripe_ok or mock_ok) else "Enable PAYMENT_STRIPE_ENABLED or PAYMENT_MOCK (sandbox)",
            usage_constraint="wallet_topup",
            subscription_recurring_eligible=True,
        ),
        method(
            "apple_pay",
            "Apple Pay",
            enabled=stripe_ok,
            providers=["stripe"] if stripe_ok else [],
            disabled_reason="Requires Stripe Checkout; wallets shown by Stripe when supported",
            usage_constraint="wallet_topup",
            subscription_recurring_eligible=False,
        ),
        method(
            "google_pay",
            "Google Pay",
            enabled=stripe_ok,
            providers=["stripe"] if stripe_ok else [],
            disabled_reason="Requires Stripe Checkout; wallets shown by Stripe when supported",
            usage_constraint="wallet_topup",
            subscription_recurring_eligible=False,
        ),
        method(
            "paypal",
            "PayPal (via Stripe Link)",
            enabled=stripe_ok and "link" in settings.payment_stripe_method_types.lower(),
            providers=["stripe"],
            disabled_reason="Add `link` to PAYMENT_STRIPE_METHOD_TYPES where Stripe supports PayPal",
            usage_constraint="wallet_topup",
            subscription_recurring_eligible=False,
        ),
        method(
            "paypal_subscriptions",
            "PayPal Subscriptions (direct API)",
            enabled=False,
            providers=["paypal"],
            disabled_reason="Direct PayPal Subscriptions / Billing API not wired in this repo; deposit uses Stripe or stub",
            usage_constraint="subscription_recurring_only",
            subscription_recurring_eligible=True,
            requires_active_checkout=False,
        ),
        method(
            "alipay",
            "Alipay",
            enabled=stripe_ok and "alipay" in settings.payment_stripe_method_types.lower(),
            providers=["stripe"],
            disabled_reason="Add `alipay` to PAYMENT_STRIPE_METHOD_TYPES (region-dependent)",
            usage_constraint="wallet_topup_only",
            subscription_recurring_eligible=False,
        ),
        method(
            "wechat_pay",
            "WeChat Pay",
            enabled=stripe_ok and "wechat_pay" in settings.payment_stripe_method_types.lower(),
            providers=["stripe"],
            disabled_reason="Add `wechat_pay` to PAYMENT_STRIPE_METHOD_TYPES (region-dependent)",
            usage_constraint="wallet_topup_only",
            subscription_recurring_eligible=False,
        ),
        method(
            "wise_bank",
            "Wise (bank / payout events)",
            enabled=wise_ingest,
            providers=["wise"],
            disabled_reason=(
                "Enable PAYMENT_WISE_WEBHOOK_ENABLED and secret; "
                "see docs/payment_international_prompt14.md"
            ),
            usage_constraint="payout_and_treasury_events",
            subscription_recurring_eligible=False,
            requires_active_checkout=False,
        ),
        method(
            "paypal_stub_webhook",
            "PayPal webhook (dev stub)",
            enabled=paypal_stub and (env == "sandbox" or not settings.production),
            providers=["paypal_stub"],
            disabled_reason="Sandbox/dev only unless explicitly enabled with secrets",
            usage_constraint="webhook_ingest_test",
            subscription_recurring_eligible=False,
            requires_active_checkout=False,
        ),
    ]

    return {
        "schema_version": "payment-capabilities-v2",
        "checkout_mode": "payment",
        "checkout_enabled": master,
        "environment": env,
        "commercial_enabled": settings.commercial_enabled,
        "payment_checkout_enabled": settings.payment_checkout_enabled,
        "stripe_checkout_events": [
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.async_payment_failed",
        ],
        "providers": {
            "stripe": {
                "enabled": stripe_ok,
                "live_ready": env == "live" and stripe_ok,
            },
            "mock": {
                "enabled": mock_ok,
                "note": "Sandbox test provider; complete via POST /v1/commerce/payments/webhooks/mock",
            },
            "wise": {
                "webhook_ingest_enabled": wise_ingest,
                "note": "Inbound webhooks for treasury / transfer state; not a customer Checkout button",
            },
            "paypal_stub": {
                "webhook_test_enabled": paypal_stub,
            },
        },
        "methods": methods,
    }
