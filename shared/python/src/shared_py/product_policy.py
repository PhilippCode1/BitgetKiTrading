"""
Feste Produktvorgaben und kommerzielle Gates (Modul Mate GmbH).

Bezug: docs/PRODUCT_BRIEF_MODUL_MATE.md (Prompt 1).

Die Funktionen hier sind reine Fachlogik-Helfer; Persistenz (Vertrag, Freigaben)
liegt in den Services. Secrets und personenbezogene Daten gehoeren nicht in diese Datei.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

PRODUCT_BRIEF_DOCUMENT_ID = "PRODUCT_BRIEF_MODUL_MATE"
PRODUCT_POLICY_MODULE_VERSION = "1.0.0"

# --- [FEST] Stakeholder-Vorgaben ---

ORGANIZATION_LEGAL_NAME = "Modul Mate GmbH"

# Fester Bezug fuer Audit-Texte und UI-Kopien (kein Ersatz fuer technische Auth-Pruefung).
SUPER_ADMIN_CANONICAL_NAME = "Philipp Crljic"

# 3 Wochen Probephase
TRIAL_PERIOD_DAYS = 21

# --- [ANNAHME] Standard bis explizite Produktentscheidung ---

# Echtgeld-Ausfuehrung zusaetzlich zu Vertrag + Admin-Freigabe an Zahlungsstatus koppeln.
REQUIRE_ACTIVE_SUBSCRIPTION_FOR_LIVE_TRADING = True


class CommercialExecutionMode(str, Enum):
    """Welcher Ausfuehrungspfad fuer Orders vorgesehen ist."""

    NONE = "none"
    DEMO = "demo"
    LIVE = "live"


@dataclass(frozen=True)
class CustomerCommercialGates:
    """
    Minimale boolesche Gates fuer Entscheidungen in Services (DB-Felder abbilden).

    Semantik:
    - trial_active: Probephase laeuft (Kalenderlogik liegt ausserhalb).
    - contract_accepted: rechtswirksam angenommene Vereinbarung liegt vor.
    - admin_live_trading_granted: Philipp (Super-Admin) hat Echtgeld freigegeben.
    - subscription_active: Abo / Zahlungsstatus in Ordnung (falls gekoppelt).
    - account_suspended: harte Sperre (Compliance, Betrug, manuell).
    - account_paused: weiche Pause (Zahlung, Nutzerwunsch).
    """

    trial_active: bool
    contract_accepted: bool
    admin_live_trading_granted: bool
    subscription_active: bool
    account_suspended: bool = False
    account_paused: bool = False


def trial_period_days() -> int:
    """Kalendertage Probephase ([FEST])."""
    return TRIAL_PERIOD_DAYS


def super_admin_display_name() -> str:
    """Anzeige- und Audit-Name des einzigen Voll-Admins ([FEST])."""
    return SUPER_ADMIN_CANONICAL_NAME


def organization_display_name() -> str:
    return ORGANIZATION_LEGAL_NAME


def resolve_execution_mode(gates: CustomerCommercialGates) -> CommercialExecutionMode:
    """
    Ermittelt den erlaubten kommerziellen Ausfuehrungsmodus.

    Regeln [FEST]:
    - Gesperrt oder pausiert: keine Ausfuehrung.
    - Ohne Admin-Freigabe oder ohne Vertrag: kein Echtgeld; Demo nur wenn sinnvoll (Probephase
      oder Vertrag kann Demo erlauben – hier: Demo wenn Trial aktiv ODER Vertrag da, aber nicht Live).

    Vereinfachung [ANNAHME]:
    - Demo-Trading ist waehrend aktiver Probephase erlaubt (auch ohne Vertrag).
    - Nach Vertrag ohne Live-Freigabe: weiter Demo (realistisches Erlebnis ohne Echtgeld).
    - Live nur bei Vertrag + Admin-Freigabe + nicht gesperrt/pausiert + optional Abo.
    """
    if gates.account_suspended or gates.account_paused:
        return CommercialExecutionMode.NONE

    live_ok = gates.contract_accepted and gates.admin_live_trading_granted
    if REQUIRE_ACTIVE_SUBSCRIPTION_FOR_LIVE_TRADING:
        live_ok = live_ok and gates.subscription_active

    if live_ok:
        return CommercialExecutionMode.LIVE

    if gates.trial_active or gates.contract_accepted:
        return CommercialExecutionMode.DEMO

    return CommercialExecutionMode.NONE


def live_trading_allowed(gates: CustomerCommercialGates) -> bool:
    """True genau dann, wenn Echtgeld-Orders laut Produktregeln erlaubt sind."""
    return resolve_execution_mode(gates) == CommercialExecutionMode.LIVE


def demo_trading_allowed(gates: CustomerCommercialGates) -> bool:
    """True, wenn Uebungs-/Demo-Ausfuehrung erlaubt ist."""
    return resolve_execution_mode(gates) == CommercialExecutionMode.DEMO


def can_place_live_orders(gates: CustomerCommercialGates) -> bool:
    """
    Explizite API-Semantik: Echtgeld-Exchange-Submit (nicht Paper).

    Aequivalent zu `live_trading_allowed` — eigener Name fuer BFF/Audit/Contracts.
    """
    return live_trading_allowed(gates)


def can_place_demo_orders(gates: CustomerCommercialGates) -> bool:
    """
    Explizite API-Semantik: Demo-/Uebungspfad (kein Live-Geld).

    Aequivalent zu `demo_trading_allowed` — strikt getrennt von Live.
    """
    return demo_trading_allowed(gates)


@dataclass(frozen=True)
class OrderPlacementPermissions:
    """Kanonische Booleans fuer Clients (keine Vermischung Demo vs. Live)."""

    can_place_demo_orders: bool
    can_place_live_orders: bool
    commercial_execution_mode: CommercialExecutionMode


def order_placement_permissions(
    gates: CustomerCommercialGates,
) -> OrderPlacementPermissions:
    """Leitet Demo- und Live-Erlaubnis getrennt aus denselben Quell-Gates ab."""
    mode = resolve_execution_mode(gates)
    return OrderPlacementPermissions(
        can_place_demo_orders=(mode == CommercialExecutionMode.DEMO),
        can_place_live_orders=(mode == CommercialExecutionMode.LIVE),
        commercial_execution_mode=mode,
    )


def telegram_live_actions_allowed(gates: CustomerCommercialGates) -> bool:
    """
    Telegram darf Aktionen ausloesen, die Echtgeld beruehren, nur wenn Live-Handel erlaubt ist.

    [ANNAHME] Zusaetzliche OTP-/Bestaetigungsstufen werden in den jeweiligen Services erzwungen.
    """
    return live_trading_allowed(gates)


def exchange_api_connection_allowed(
    gates: CustomerCommercialGates,
    *,
    purpose: Literal["read_only_health", "demo_execution", "live_execution"],
) -> tuple[bool, str]:
    """
    Grobe Policy fuer API-Nutzung (ohne technische Credential-Pruefung).

    Returns:
        (erlaubt, kurzer Grundcode fuer Logs; Grundcodes stabil halten).
    """
    if gates.account_suspended:
        return False, "account_suspended"
    if purpose == "live_execution":
        if not live_trading_allowed(gates):
            return False, "live_trading_not_permitted"
        return True, "ok"
    if purpose == "demo_execution":
        if demo_trading_allowed(gates):
            return True, "ok"
        return False, "demo_not_permitted"
    # read_only_health
    if gates.account_paused and not gates.trial_active:
        return False, "account_paused"
    return True, "ok"


class ExecutionPolicyViolationError(ValueError):
    """
    Harter Stopp: LIVE-Ausfuehrung/Submit nicht erlaubt (Vertrag, Gates, Modus).
    Fuer produktive Live-Broker-Pfade — nicht vor Bitget-Order-API weiterreichen.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def product_policy_descriptor() -> dict[str, str | int | bool]:
    """Diagnose: welche Policy-Version und Kernkonstanten aktiv sind."""
    return {
        "product_policy_module_version": PRODUCT_POLICY_MODULE_VERSION,
        "product_brief_document_id": PRODUCT_BRIEF_DOCUMENT_ID,
        "organization_legal_name": ORGANIZATION_LEGAL_NAME,
        "super_admin_canonical_name": SUPER_ADMIN_CANONICAL_NAME,
        "trial_period_days": TRIAL_PERIOD_DAYS,
        "require_active_subscription_for_live_trading": REQUIRE_ACTIVE_SUBSCRIPTION_FOR_LIVE_TRADING,
    }
