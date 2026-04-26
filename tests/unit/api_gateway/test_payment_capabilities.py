"""Payment capabilities: keine Secrets, Feature-Flags."""

from __future__ import annotations

from api_gateway.payments.capabilities import build_payment_capabilities

from config.gateway_settings import GatewaySettings


def _gw(**kwargs: object) -> GatewaySettings:
    defaults: dict[str, object] = {
        "production": False,
        "commercial_enabled": True,
        "payment_checkout_enabled": True,
        "payment_mode": "sandbox",
        "payment_stripe_enabled": True,
        "payment_stripe_secret_key": "sk_test_dummy",
        "payment_stripe_webhook_secret": "",
        "payment_stripe_success_url": "https://example.com/ok",
        "payment_stripe_cancel_url": "https://example.com/cancel",
        "payment_stripe_method_types": "card,link,alipay,wechat_pay",
        "payment_mock_enabled": True,
        "payment_mock_webhook_secret": "x" * 32,
        "payment_wise_webhook_enabled": False,
        "payment_wise_webhook_secret": "",
        "payment_paypal_stub_webhook_enabled": False,
        "payment_paypal_stub_webhook_secret": "",
    }
    defaults.update(kwargs)
    return GatewaySettings.model_construct(**defaults)  # type: ignore[arg-type]


def test_capabilities_master_off_when_commercial_disabled() -> None:
    cap = build_payment_capabilities(_gw(commercial_enabled=False))
    assert cap["checkout_enabled"] is False
    assert cap["methods"][0]["enabled"] is False


def test_paypal_flag_follows_link_method_type() -> None:
    cap = build_payment_capabilities(_gw(payment_stripe_method_types="card"))
    paypal = next(m for m in cap["methods"] if m["id"] == "paypal")
    assert paypal["enabled"] is False

    cap2 = build_payment_capabilities(_gw(payment_stripe_method_types="card,link"))
    paypal2 = next(m for m in cap2["methods"] if m["id"] == "paypal")
    assert paypal2["enabled"] is True


def test_live_requires_webhook_secret_for_stripe_ready() -> None:
    cap = build_payment_capabilities(
        _gw(payment_mode="live", payment_stripe_webhook_secret="whsec_" + "y" * 24)
    )
    assert cap["environment"] == "live"
    assert cap["providers"]["stripe"]["live_ready"] is True


def test_capabilities_schema_v2_and_stripe_async_events() -> None:
    cap = build_payment_capabilities(_gw())
    assert cap["schema_version"] == "payment-capabilities-v2"
    assert "checkout.session.async_payment_succeeded" in cap["stripe_checkout_events"]
    assert "checkout.session.async_payment_failed" in cap["stripe_checkout_events"]
    assert "wise" in cap["providers"]


def test_wise_rail_enabled_without_stripe_checkout_master() -> None:
    """Wise-Ingest darf bei ausgeschaltetem Checkout weiterhin signalisierbar sein."""
    cap = build_payment_capabilities(
        _gw(
            payment_checkout_enabled=False,
            payment_wise_webhook_enabled=True,
            payment_wise_webhook_secret="w" * 32,
        )
    )
    assert cap["checkout_enabled"] is False
    wise_m = next(m for m in cap["methods"] if m["id"] == "wise_bank")
    assert wise_m["enabled"] is True
    assert cap["providers"]["wise"]["webhook_ingest_enabled"] is True
