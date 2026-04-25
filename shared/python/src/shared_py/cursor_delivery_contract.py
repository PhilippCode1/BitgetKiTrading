"""
LLM/Assist-Liefermodus: Antwortformat, Abschnitte, Kennzeichner (unveraenderte Konstanten, Kompatibilitaet).

Historische Dokument-ID; Spezifikation in diesem Modul und zugehoerigen Vertragsdateien.

Dient als maschinenlesbare Referenz fuer Skripte, CI-Hinweise oder Generator-Tools.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

CURSOR_DELIVERY_CONTRACT_VERSION = "1.0.0"
CURSOR_DELIVERY_DOCUMENT_ID = "CURSOR_IMPLEMENTATION_MODE_MODUL_MATE"

# --- Festes Antwortformat (Ueberschriften fuer Chat/PR) ---

RESPONSE_SECTION_TITLES_DE: Final[tuple[str, ...]] = (
    "Ziel des Schritts",
    "Betroffene Dateien",
    "Vollstaendige Dateien",
    "Kurze Testanleitung",
    "Bekannte offene Punkte",
)

# --- Kennzeichnung technischer Schulden / Risiken (im Code oder Git-Message) ---

DELIVERY_MARKER_TECHNICAL_DEBT: Final[str] = "[TECHNICAL_DEBT]"
DELIVERY_MARKER_PROVISIONAL: Final[str] = "[PROVISIONAL]"
DELIVERY_MARKER_RISK: Final[str] = "[RISK]"
DELIVERY_MARKER_FUTURE: Final[str] = "[FUTURE]"


class ImplementationPhaseId(str, Enum):
    """
    Logische Bauabschnitte — Reihenfolge fuer schrittweise Umsetzung.

    BA00 entspricht den bereits angelegten Policy-/Design-Kontrakten.
    """

    BA00_CONTRACTS_AND_DOCS = "ba00_contracts_and_docs"
    BA01_DATABASE_DOMAIN = "ba01_database_domain"
    BA02_AUTH_SESSION = "ba02_auth_session"
    BA03_CUSTOMER_API = "ba03_customer_api"
    BA04_ADMIN_API = "ba04_admin_api"
    BA05_PAYMENTS_PSP = "ba05_payments_psp"
    BA06_TRADING_GATES = "ba06_trading_gates"
    BA07_AI_WIRING = "ba07_ai_wiring"
    BA08_TELEGRAM = "ba08_telegram"
    BA09_FRONTEND_CUSTOMER = "ba09_frontend_customer"
    BA10_FRONTEND_ADMIN = "ba10_frontend_admin"
    BA11_E2E_HARDENING = "ba11_e2e_hardening"


IMPLEMENTATION_PHASE_ORDER: Final[tuple[ImplementationPhaseId, ...]] = tuple(ImplementationPhaseId)


def phase_index(phase: ImplementationPhaseId) -> int:
    return IMPLEMENTATION_PHASE_ORDER.index(phase)


def response_checklist_de() -> list[str]:
    """Kurzcheck fuer Agenten/Menschen vor dem Absenden einer Umsetzungsantwort."""
    return [
        "Jede gelieferte Datei ist vollstaendig (keine ausgelassenen Bereiche).",
        "Keine erfundenen Pfade — nur repo-konsistente Aenderungen.",
        "Testanleitung genannt oder Tests ausgefuehrt.",
        "Offene Punkte explizit aufgelistet.",
        "Bei Annahmen: Liste + Standardentscheidung gegeben.",
    ]


def cursor_delivery_descriptor() -> dict[str, str | int]:
    return {
        "cursor_delivery_contract_version": CURSOR_DELIVERY_CONTRACT_VERSION,
        "cursor_delivery_document_id": CURSOR_DELIVERY_DOCUMENT_ID,
        "implementation_phases": len(ImplementationPhaseId),
        "response_sections": len(RESPONSE_SECTION_TITLES_DE),
    }
