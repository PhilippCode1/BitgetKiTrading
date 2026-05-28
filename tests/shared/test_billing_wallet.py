import uuid
from decimal import Decimal

from shared_py.billing_wallet import (
    compute_daily_charge_amount,
    payment_deposit_wallet_idempotency_key,
    prepaid_allows_new_trade,
)


def test_prepaid_allows_at_threshold() -> None:
    ok, _ = prepaid_allows_new_trade(Decimal("50"), min_activation_usd=Decimal("50"))
    assert ok
    ok2, msg = prepaid_allows_new_trade(
        Decimal("49.99"), min_activation_usd=Decimal("50")
    )
    assert not ok2
    assert "min_activation" in msg


def test_daily_charge_never_negative_balance() -> None:
    assert compute_daily_charge_amount(
        Decimal("200"), daily_fee_usd=Decimal("50")
    ) == Decimal("50")
    assert compute_daily_charge_amount(
        Decimal("30"), daily_fee_usd=Decimal("50")
    ) == Decimal("30")
    assert compute_daily_charge_amount(
        Decimal("0"), daily_fee_usd=Decimal("50")
    ) == Decimal("0")


def test_payment_deposit_wallet_idempotency_key_is_stable() -> None:
    i = uuid.uuid4()
    a = payment_deposit_wallet_idempotency_key(intent_id=i)
    b = payment_deposit_wallet_idempotency_key(intent_id=i)
    assert a == b
    assert str(i) in a
