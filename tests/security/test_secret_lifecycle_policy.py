from __future__ import annotations

from datetime import date

from shared_py.secret_lifecycle import (
    build_secret_rotation_audit_payload,
    classify_secret_name,
    secret_is_expired,
    secret_requires_rotation,
    secret_reuse_across_env_is_forbidden,
    secret_rotation_interval_days,
)


def test_bitget_secrets_require_rotation() -> None:
    assert secret_requires_rotation("BITGET_API_KEY")
    assert secret_requires_rotation("BITGET_API_SECRET")
    assert secret_rotation_interval_days("BITGET_API_PASSPHRASE") == 30


def test_jwt_secrets_require_rotation() -> None:
    assert secret_requires_rotation("JWT_SECRET")
    assert secret_rotation_interval_days("GATEWAY_JWT_SECRET") == 30


def test_admin_token_requires_rotation_or_short_ttl() -> None:
    assert secret_requires_rotation("ADMIN_TOKEN")
    assert secret_rotation_interval_days("ADMIN_TOKEN") <= 14


def test_reuse_across_local_shadow_production_forbidden() -> None:
    assert secret_reuse_across_env_is_forbidden("OPENAI_API_KEY")
    assert secret_reuse_across_env_is_forbidden("JWT_SECRET")


def test_expired_secret_detected() -> None:
    assert secret_is_expired(
        "JWT_SECRET",
        last_rotated_at=date(2026, 1, 1),
        as_of=date(2026, 3, 5),
    )


def test_unknown_secret_treated_sensitive() -> None:
    policy = classify_secret_name("NEW_VENDOR_ACCESS_TOKEN")
    assert policy.sensitivity == "high"
    assert policy.expiry_expected
    assert policy.rotation_interval_days == 30


def test_customer_exchange_secret_highest_sensitivity() -> None:
    policy = classify_secret_name("customer_bitget_api_secret")
    assert policy.id == "CUSTOMER_EXCHANGE_SECRET_REFERENCE"
    assert policy.sensitivity == "critical"


def test_rotation_audit_payload_has_owner_env_reason() -> None:
    payload = build_secret_rotation_audit_payload(
        "BITGET_API_KEY",
        owner="Trading Operations",
        environment="shadow",
        reason="scheduled_rotation",
        last_rotated_at=date(2026, 1, 1),
        as_of=date(2026, 2, 5),
    )
    assert payload["owner"] == "Trading Operations"
    assert payload["environment"] == "shadow"
    assert payload["reason"] == "scheduled_rotation"
    assert payload["expired"] is True
