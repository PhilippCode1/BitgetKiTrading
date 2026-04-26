"""Tests fuer shared_py.cursor_delivery_contract (Prompt 10)."""

from __future__ import annotations

from shared_py.cursor_delivery_contract import (
    DELIVERY_MARKER_FUTURE,
    DELIVERY_MARKER_PROVISIONAL,
    IMPLEMENTATION_PHASE_ORDER,
    RESPONSE_SECTION_TITLES_DE,
    ImplementationPhaseId,
    cursor_delivery_descriptor,
    phase_index,
    response_checklist_de,
)


def test_response_sections_five() -> None:
    assert len(RESPONSE_SECTION_TITLES_DE) == 5
    assert "Vollstaendige Dateien" in RESPONSE_SECTION_TITLES_DE


def test_phases_ordered_ba00_first() -> None:
    assert IMPLEMENTATION_PHASE_ORDER[0] == ImplementationPhaseId.BA00_CONTRACTS_AND_DOCS


def test_phase_index_monotonic() -> None:
    assert phase_index(ImplementationPhaseId.BA01_DATABASE_DOMAIN) < phase_index(
        ImplementationPhaseId.BA11_E2E_HARDENING
    )


def test_checklist_nonempty() -> None:
    assert len(response_checklist_de()) >= 4
    assert any("vollstaendig" in x.lower() for x in response_checklist_de())


def test_markers_distinct() -> None:
    assert DELIVERY_MARKER_PROVISIONAL != DELIVERY_MARKER_FUTURE


def test_descriptor() -> None:
    d = cursor_delivery_descriptor()
    assert d["implementation_phases"] == len(ImplementationPhaseId)
