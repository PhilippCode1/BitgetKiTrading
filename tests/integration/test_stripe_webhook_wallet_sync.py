"""
Prompt 42: Valider Stripe-Webhook (Signatur) -> customer_wallet, idempotent pro Checkout-Session.
Benötigt TEST_DATABASE_URL (Postgres) und vollstaendige Commerce-Migrationen.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

try:
    from stripe import Webhook
    from stripe._webhook import WebhookSignature
except ImportError:
    Webhook = None  # type: ignore[assignment, misc]
    WebhookSignature = None  # type: ignore[assignment, misc]

try:
    import stripe
except ImportError:
    stripe = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    not (os.getenv("TEST_DATABASE_URL") or "").strip(),
    reason="TEST_DATABASE_URL required",
)

WHSEC = "whsec_test_stripe_webhook_secret_for_prompt42"


def _build_stripe_signature_header(body: bytes, secret: str) -> str:
    if WebhookSignature is None:
        raise RuntimeError("stripe not installed")
    ts = int(time.time())
    signed = f"{ts}.{body.decode('utf-8')}"
    dig = WebhookSignature._compute_signature(signed, secret)  # noqa: SLF001
    return f"t={ts},v1={dig}"


def _stash_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMERCIAL_ENABLED", "1")
    monkeypatch.setenv("PAYMENT_CHECKOUT_ENABLED", "1")
    monkeypatch.setenv("PAYMENT_STRIPE_ENABLED", "1")
    monkeypatch.setenv("PAYMENT_STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("PAYMENT_STRIPE_WEBHOOK_SECRET", WHSEC)
    monkeypatch.setenv("PAYMENT_STRIPE_SUCCESS_URL", "https://example.com/ok")
    monkeypatch.setenv("PAYMENT_STRIPE_CANCEL_URL", "https://example.com/cancel")


def _insert_minimal_tenant_and_intent(
    conn: Any, *, tid: str, iid: UUID, session_id: str, amount: Decimal
) -> None:
    cur = conn.execute(
        "SELECT 1 FROM app.commercial_plan_definitions WHERE plan_id = 'default' LIMIT 1"
    ).fetchone()
    if not cur:
        conn.execute(
            """
            INSERT INTO app.commercial_plan_definitions (plan_id, display_name, entitlements_json)
            VALUES ('default', 'Test', '{}'::jsonb)
            ON CONFLICT (plan_id) DO NOTHING
            """
        )
    conn.execute(
        """
        INSERT INTO app.tenant_commercial_state (tenant_id, plan_id, budget_cap_usd_month)
        VALUES (%s, 'default', 1000)
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        (tid,),
    )
    conn.execute(
        """
        INSERT INTO app.customer_wallet (tenant_id, prepaid_balance_list_usd)
        VALUES (%s, 0)
        ON CONFLICT (tenant_id) DO UPDATE SET
            prepaid_balance_list_usd = app.customer_wallet.prepaid_balance_list_usd
        """,
        (tid,),
    )
    conn.execute(
        """
        INSERT INTO app.payment_deposit_intent (
            intent_id, tenant_id, idempotency_key, provider, environment,
            amount_list_usd, currency, status, provider_checkout_session_id
        ) VALUES (
            %s, %s, 'idem-1', 'stripe', 'sandbox', %s, 'USD', 'awaiting_payment', %s
        )
        """,
        (str(iid), tid, str(amount), session_id[:255]),
    )


def _build_checkout_session_event(
    *,
    event_id: str,
    session_id: str,
    intent_id: UUID,
    tenant_id: str,
    amount_minor: int,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_status": "paid",
                "amount_total": amount_minor,
                "currency": "usd",
                "metadata": {
                    "tenant_id": tenant_id,
                    "intent_id": str(intent_id),
                },
                "payment_intent": "pi_test_123",
                "payment_method_types": ["card"],
            }
        },
    }


@pytest.mark.integration
def test_stripe_checkout_paid_webhook_credits_idempotent(
    integration_postgres_conn: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    if Webhook is None or stripe is None:
        pytest.skip("stripe package required")
    _stash_env(monkeypatch)
    from api_gateway.payments.deposit import process_stripe_webhook_payload

    from config.gateway_settings import GatewaySettings

    tid = f"itest_stripe_{uuid.uuid4().hex[:10]}"
    iid = uuid.uuid4()
    sid = f"cs_test_{uuid.uuid4().hex[:12]}"
    amt = Decimal("12.34")
    minor = int(amt * 100)
    event_id = f"evt_{uuid.uuid4().hex[:20]}"
    conn = integration_postgres_conn

    with conn.transaction():
        _insert_minimal_tenant_and_intent(
            conn, tid=tid, iid=iid, session_id=sid, amount=amt
        )

    settings = GatewaySettings()
    ev = _build_checkout_session_event(
        event_id=event_id,
        session_id=sid,
        intent_id=iid,
        tenant_id=tid,
        amount_minor=minor,
    )
    raw = json.dumps(ev, separators=(",", ":")).encode("utf-8")
    sig = _build_stripe_signature_header(raw, WHSEC)

    with conn.transaction():
        out1 = process_stripe_webhook_payload(
            conn, settings, payload=raw, sig_header=sig
        )
    assert out1.get("handled") is True
    with conn.transaction():
        out2 = process_stripe_webhook_payload(
            conn, settings, payload=raw, sig_header=sig
        )
    assert out2.get("handled") is True

    row = conn.execute(
        "SELECT prepaid_balance_list_usd FROM app.customer_wallet WHERE tenant_id = %s",
        (tid,),
    ).fetchone()
    assert row is not None
    assert Decimal(str(dict(row)["prepaid_balance_list_usd"])) == amt
    n_inbox = conn.execute(
        """
        SELECT outcome FROM app.payment_webhook_inbox
        WHERE provider = 'stripe' AND provider_event_id = %s
        """,
        (f"stripe:checkout_paid:{sid}",),
    ).fetchone()
    assert n_inbox is not None
    assert str(dict(n_inbox)["outcome"]) == "succeeded"


@pytest.mark.integration
def test_reconcile_second_pass_no_op_without_double_credit(
    integration_postgres_conn: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    if Webhook is None or stripe is None:
        pytest.skip("stripe package required")
    _stash_env(monkeypatch)
    from api_gateway.payments import deposit as dep
    from api_gateway.payments import stripe_checkout as sc

    from config.gateway_settings import GatewaySettings

    tid = f"itest_recon_{uuid.uuid4().hex[:10]}"
    iid = uuid.uuid4()
    sid = f"cs_test_{uuid.uuid4().hex[:12]}"
    amt = Decimal("5.00")
    ev = _build_checkout_session_event(
        event_id="evt_ignored",
        session_id=sid,
        intent_id=iid,
        tenant_id=tid,
        amount_minor=500,
    )
    session_d = ev["data"]["object"]  # type: ignore[assignment]

    conn = integration_postgres_conn
    with conn.transaction():
        _insert_minimal_tenant_and_intent(
            conn, tid=tid, iid=iid, session_id=sid, amount=amt
        )

    settings = GatewaySettings()
    calls = [0]

    def _mock_retrieve(_s: Any, **kw: Any) -> dict[str, Any] | None:  # noqa: ANN401
        calls[0] += 1
        if isinstance(kw.get("session_id"), str) and "cs_test" in kw["session_id"]:
            return session_d  # type: ignore[return-value]
        return None

    monkeypatch.setattr(
        sc, "retrieve_checkout_session_for_reconciliation", _mock_retrieve
    )
    with conn.transaction():
        n1 = dep.reconcile_stripe_deposits_for_tenant(conn, settings, tenant_id=tid)
    assert n1 == 1
    with conn.transaction():
        n2 = dep.reconcile_stripe_deposits_for_tenant(conn, settings, tenant_id=tid)
    assert n2 == 0
    b = conn.execute(
        "SELECT prepaid_balance_list_usd FROM app.customer_wallet WHERE tenant_id = %s",
        (tid,),
    ).fetchone()
    assert b is not None
    assert Decimal(str(dict(b)["prepaid_balance_list_usd"])) == Decimal("5")
    assert calls[0] == 1
