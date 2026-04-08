"""Tests fuer shared_py.design_system_contract (Prompt 9)."""

from __future__ import annotations

from shared_py.design_system_contract import (
    CONTENT_MAX_WIDTH_PX,
    FORBIDDEN_USER_VISIBLE_TERMS,
    SPACING_PX,
    TYPOGRAPHY_SIZE_BODY_PX,
    ButtonVariant,
    SemanticStatusTone,
    admin_uses_compact_tables_default,
    copy_may_contain_forbidden_term,
    design_system_descriptor,
)


def test_content_max_width_reasonable() -> None:
    assert 960 <= CONTENT_MAX_WIDTH_PX <= 1280


def test_spacing_monotonic() -> None:
    assert list(SPACING_PX) == sorted(SPACING_PX)


def test_body_text_minimum_for_ios() -> None:
    assert TYPOGRAPHY_SIZE_BODY_PX >= 16


def test_forbidden_terms_nonempty() -> None:
    assert len(FORBIDDEN_USER_VISIBLE_TERMS) >= 20


def test_copy_detects_api_word() -> None:
    assert copy_may_contain_forbidden_term("Bitte API pruefen") is True


def test_copy_allows_plain_german() -> None:
    assert copy_may_contain_forbidden_term("Ihre Zahlung ist eingegangen.") is False


def test_tokenize_not_flagged() -> None:
    assert copy_may_contain_forbidden_term("Wir tokenisieren nichts.") is False


def test_admin_compact_default() -> None:
    assert admin_uses_compact_tables_default() is True


def test_enums_distinct() -> None:
    assert len(ButtonVariant) >= 4
    assert len(SemanticStatusTone) >= 4


def test_descriptor() -> None:
    d = design_system_descriptor()
    assert d["forbidden_term_count"] == len(FORBIDDEN_USER_VISIBLE_TERMS)
