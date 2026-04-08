"""Tests fuer shared_py.admin_console_contract (Prompt 5)."""

from __future__ import annotations

from shared_py.admin_console_contract import (
    ADMIN_CONSOLE_BASE_PATH,
    ACTION_CONFIRMATION_TIER,
    ACTION_LABELS_DE,
    ACTION_WARNING_LEVEL,
    AdminActionId,
    ConfirmationTier,
    CustomerDetailTabId,
    EXPLAIN_PLACEHOLDER_TITLE_DE,
    KPI_LABELS_DE,
    UiWarningLevel,
    admin_console_descriptor,
    admin_path,
    all_admin_nav_paths,
    customer_detail_path,
    requires_reason_note,
    super_admin_display_name_de,
)


def test_admin_path_home() -> None:
    assert admin_path("") == ADMIN_CONSOLE_BASE_PATH


def test_admin_path_segment() -> None:
    assert admin_path("/kunden") == f"{ADMIN_CONSOLE_BASE_PATH}/kunden"
    assert admin_path("kunden") == f"{ADMIN_CONSOLE_BASE_PATH}/kunden"


def test_all_nav_paths_unique() -> None:
    paths = all_admin_nav_paths()
    assert len(paths) == len(set(paths))


def test_all_nav_paths_under_base() -> None:
    for p in all_admin_nav_paths():
        assert p.startswith(ADMIN_CONSOLE_BASE_PATH)


def test_customer_detail_path() -> None:
    p = customer_detail_path("cust-42", CustomerDetailTabId.CONTRACT)
    assert "cust-42" in p
    assert CustomerDetailTabId.CONTRACT.value in p


def test_kpi_labels_german_no_underscores_visible() -> None:
    for kpi, label in KPI_LABELS_DE.items():
        assert kpi.value
        assert "_" not in label
        assert len(label) >= 3


def test_action_labels_no_api_jargon() -> None:
    bad = ("api_", "json", "sql", "http_")
    for _aid, label in ACTION_LABELS_DE.items():
        lower = label.lower()
        assert not any(b in lower for b in bad)


def test_global_kill_switch_type_confirm() -> None:
    assert (
        ACTION_CONFIRMATION_TIER[AdminActionId.GLOBAL_PAUSE_LIVE_TRADING]
        == ConfirmationTier.TYPE_TO_CONFIRM
    )
    assert ACTION_WARNING_LEVEL[AdminActionId.GLOBAL_PAUSE_LIVE_TRADING] == UiWarningLevel.CRITICAL


def test_recheck_exchange_no_dialog_tier() -> None:
    assert ACTION_CONFIRMATION_TIER[AdminActionId.RECHECK_EXCHANGE_CONNECTION] == ConfirmationTier.NONE


def test_grant_live_double_confirm() -> None:
    assert ACTION_CONFIRMATION_TIER[AdminActionId.GRANT_LIVE_TRADING] == ConfirmationTier.DOUBLE_CONFIRM


def test_requires_reason_for_critical() -> None:
    assert requires_reason_note(AdminActionId.GRANT_LIVE_TRADING) is True
    assert requires_reason_note(AdminActionId.RECHECK_EXCHANGE_CONNECTION) is False


def test_super_admin_name_matches_product_policy() -> None:
    assert "Philipp" in super_admin_display_name_de()


def test_descriptor() -> None:
    d = admin_console_descriptor()
    assert d["primary_nav_entries"] >= 8


def test_explain_placeholder_human() -> None:
    assert "erklaert" in EXPLAIN_PLACEHOLDER_TITLE_DE.lower()
