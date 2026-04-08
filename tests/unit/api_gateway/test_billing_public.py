from decimal import Decimal

from api_gateway.billing.daily_run import build_billing_status_public


def test_billing_status_levels() -> None:
    s = build_billing_status_public(
        prepaid_balance_list_usd=Decimal("120"),
        daily_fee_usd=Decimal("50"),
        min_new_trade_usd=Decimal("50"),
        warning_below_usd=Decimal("100"),
        critical_below_usd=Decimal("50"),
    )
    assert s["balance_level"] == "ok"
    assert s["allows_new_trades"] is True

    s2 = build_billing_status_public(
        prepaid_balance_list_usd=Decimal("75"),
        daily_fee_usd=Decimal("50"),
        min_new_trade_usd=Decimal("50"),
        warning_below_usd=Decimal("100"),
        critical_below_usd=Decimal("50"),
    )
    assert s2["balance_level"] == "warning"

    s3 = build_billing_status_public(
        prepaid_balance_list_usd=Decimal("40"),
        daily_fee_usd=Decimal("50"),
        min_new_trade_usd=Decimal("50"),
        warning_below_usd=Decimal("100"),
        critical_below_usd=Decimal("50"),
    )
    assert s3["balance_level"] == "critical"
    assert s3["allows_new_trades"] is False

    s4 = build_billing_status_public(
        prepaid_balance_list_usd=Decimal("0"),
        daily_fee_usd=Decimal("50"),
        min_new_trade_usd=Decimal("50"),
        warning_below_usd=Decimal("100"),
        critical_below_usd=Decimal("50"),
    )
    assert s4["balance_level"] == "depleted"
