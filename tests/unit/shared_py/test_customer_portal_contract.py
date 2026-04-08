"""Tests fuer shared_py.customer_portal_contract (Prompt 6)."""

from __future__ import annotations

from shared_py.customer_portal_contract import (
    CUSTOMER_PORTAL_BASE_PATH,
    CUSTOMER_PRIMARY_NAV,
    CustomerPortalPageId,
    FORBIDDEN_UX_PATTERNS,
    SUBSCRIPTION_INTERVAL_LABELS_DE,
    SubscriptionIntervalId,
    all_customer_portal_nav_paths,
    customer_portal_descriptor,
    customer_portal_path,
    page_public_title_de,
    status_mode_label_de,
    subscription_billing_explanation_de,
)


def test_customer_portal_home_path() -> None:
    assert customer_portal_path("") == CUSTOMER_PORTAL_BASE_PATH


def test_customer_portal_nested() -> None:
    assert customer_portal_path("abo") == f"{CUSTOMER_PORTAL_BASE_PATH}/abo"


def test_nav_paths_unique() -> None:
    paths = all_customer_portal_nav_paths()
    assert len(paths) == len(set(paths))


def test_nav_count_matches_required_views() -> None:
    assert len(CUSTOMER_PRIMARY_NAV) == 11


def test_subscription_intervals_all_de() -> None:
    for sid in SubscriptionIntervalId:
        assert len(SUBSCRIPTION_INTERVAL_LABELS_DE[sid]) >= 3
        assert " " in subscription_billing_explanation_de(sid) or len(subscription_billing_explanation_de(sid)) > 20


def test_status_mode_labels_plain_language() -> None:
    assert "Echtgeld" in status_mode_label_de(practice_active=False, live_active=True)
    assert "Uebung" in status_mode_label_de(practice_active=True, live_active=False)


def test_page_title_found() -> None:
    assert page_public_title_de(CustomerPortalPageId.HELP) == "Hilfe und Support"


def test_all_portal_pages_have_public_titles() -> None:
    for pid in CustomerPortalPageId:
        assert len(page_public_title_de(pid)) >= 2


def test_forbidden_ux_nonempty() -> None:
    assert len(FORBIDDEN_UX_PATTERNS) >= 5
    assert all(" " in p for p in FORBIDDEN_UX_PATTERNS)


def test_descriptor() -> None:
    d = customer_portal_descriptor()
    assert d["nav_entries"] == 11
