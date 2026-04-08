"""
Admin-Konsole: Routen, Navigation, KPIs und Aktionsschutz (Modul Mate GmbH).

Bezug: docs/ADMIN_CONSOLE_MODUL_MATE.md (Prompt 5).

Zweck: Eine zentrale, versionierte Schnittstelle fuer Frontend und API-Gateway,
damit die Verwaltungsoberflaeche nicht zerstreut wird. Alle sichtbaren Texte hier
sind bewusst **nutzerfreundlich** (keine Entwicklersprache auf Knoepfen/Menues).

Hinweis: Authentifizierung und Autorisierung (nur Philipp) implementieren die Services;
dieses Modul liefert nur **fachliche** Konstanten und Regeln.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from shared_py.product_policy import SUPER_ADMIN_CANONICAL_NAME

ADMIN_CONSOLE_CONTRACT_VERSION = "1.0.0"
ADMIN_CONSOLE_DOCUMENT_ID = "ADMIN_CONSOLE_MODUL_MATE"

# [ANNAHME] Eigener Pfad, klar vom Kundenbereich getrennt
ADMIN_CONSOLE_BASE_PATH: Final[str] = "/verwaltung"


class UiWarningLevel(str, Enum):
    """Visuelle und inhaltliche Dringlichkeit von Aktionen und Bannern."""

    INFO = "info"
    ATTENTION = "attention"
    CRITICAL = "critical"


class ConfirmationTier(str, Enum):
    """Schutz gegen Fehlbedienung bei kritischen Aenderungen."""

    NONE = "none"
    SINGLE_DIALOG = "single_dialog"
    DOUBLE_CONFIRM = "double_confirm"
    TYPE_TO_CONFIRM = "type_to_confirm"


class AdminActionId(str, Enum):
    """Stabile IDs fuer Audit und UI — nicht mit technischen API-Pfaden verwechseln."""

    TRIAL_EXTEND = "trial_extend"
    TRIAL_STOP = "trial_stop"
    GRANT_LIVE_TRADING = "grant_live_trading"
    REVOKE_LIVE_TRADING = "revoke_live_trading"
    PAUSE_CUSTOMER = "pause_customer"
    RESUME_CUSTOMER = "resume_customer"
    SUSPEND_CUSTOMER = "suspend_customer"
    UNSUSPEND_CUSTOMER = "unsuspend_customer"
    RECHECK_EXCHANGE_CONNECTION = "recheck_exchange_connection"
    REVOKE_EXCHANGE_ACCESS = "revoke_exchange_access"
    RESET_TELEGRAM_LINK = "reset_telegram_link"
    REVOKE_TELEGRAM_LIVE = "revoke_telegram_live"
    PUBLISH_PROMPT_VERSION = "publish_prompt_version"
    ROLLBACK_PROMPT_VERSION = "rollback_prompt_version"
    GLOBAL_PAUSE_LIVE_TRADING = "global_pause_live_trading"
    GLOBAL_PAUSE_AI_RESPONSES = "global_pause_ai_responses"
    GLOBAL_MAINTENANCE_MODE = "global_maintenance_mode"
    ADD_SUPPORT_NOTE = "add_support_note"


class DashboardKpiId(str, Enum):
    """Kacheln auf der Verwaltungs-Startseite."""

    PENDING_LIVE_APPROVALS = "pending_live_approvals"
    PAYMENT_ISSUES = "payment_issues"
    EXCHANGE_CONNECTION_PROBLEMS = "exchange_connection_problems"
    TELEGRAM_INCOMPLETE = "telegram_incomplete"
    EMERGENCY_ACTIVE = "emergency_active"
    NEW_CUSTOMERS_7D = "new_customers_7d"
    ACTIVE_TRIALS = "active_trials"


# Anzeigetexte fuer KPIs (deutsch, ohne Code-Sprache)
KPI_LABELS_DE: dict[DashboardKpiId, str] = {
    DashboardKpiId.PENDING_LIVE_APPROVALS: "Wartet auf Ihre Freigabe",
    DashboardKpiId.PAYMENT_ISSUES: "Zahlungen mit Hinweis",
    DashboardKpiId.EXCHANGE_CONNECTION_PROBLEMS: "Verbindungsprobleme Boerse",
    DashboardKpiId.TELEGRAM_INCOMPLETE: "Telegram unvollstaendig",
    DashboardKpiId.EMERGENCY_ACTIVE: "Notfallmodus aktiv",
    DashboardKpiId.NEW_CUSTOMERS_7D: "Neue Kunden (7 Tage)",
    DashboardKpiId.ACTIVE_TRIALS: "Aktive Probephase",
}


# Aktionsbeschriftungen fuer Primaerknoepfe / Menues (deutsch)
ACTION_LABELS_DE: dict[AdminActionId, str] = {
    AdminActionId.TRIAL_EXTEND: "Probephase verlaengern",
    AdminActionId.TRIAL_STOP: "Probephase beenden",
    AdminActionId.GRANT_LIVE_TRADING: "Echtgeld freigeben",
    AdminActionId.REVOKE_LIVE_TRADING: "Echtgeld-Freigabe zurueckziehen",
    AdminActionId.PAUSE_CUSTOMER: "Konto pausieren",
    AdminActionId.RESUME_CUSTOMER: "Pause aufheben",
    AdminActionId.SUSPEND_CUSTOMER: "Konto sperren",
    AdminActionId.UNSUSPEND_CUSTOMER: "Sperre aufheben",
    AdminActionId.RECHECK_EXCHANGE_CONNECTION: "Verbindung pruefen",
    AdminActionId.REVOKE_EXCHANGE_ACCESS: "Boersenzugriff sperren",
    AdminActionId.RESET_TELEGRAM_LINK: "Telegram-Verknuepfung zuruecksetzen",
    AdminActionId.REVOKE_TELEGRAM_LIVE: "Telegram ohne Live-Aktionen",
    AdminActionId.PUBLISH_PROMPT_VERSION: "Textversion veroeffentlichen",
    AdminActionId.ROLLBACK_PROMPT_VERSION: "Vorherige Textversion aktivieren",
    AdminActionId.GLOBAL_PAUSE_LIVE_TRADING: "Live-Handel fuer alle anhalten",
    AdminActionId.GLOBAL_PAUSE_AI_RESPONSES: "KI-Antworten anhalten",
    AdminActionId.GLOBAL_MAINTENANCE_MODE: "Wartungshinweis aktivieren",
    AdminActionId.ADD_SUPPORT_NOTE: "Notiz hinzufuegen",
}


# Welche Warnstufe im Dialog gelten soll
ACTION_WARNING_LEVEL: dict[AdminActionId, UiWarningLevel] = {
    AdminActionId.TRIAL_EXTEND: UiWarningLevel.INFO,
    AdminActionId.TRIAL_STOP: UiWarningLevel.ATTENTION,
    AdminActionId.GRANT_LIVE_TRADING: UiWarningLevel.CRITICAL,
    AdminActionId.REVOKE_LIVE_TRADING: UiWarningLevel.CRITICAL,
    AdminActionId.PAUSE_CUSTOMER: UiWarningLevel.ATTENTION,
    AdminActionId.RESUME_CUSTOMER: UiWarningLevel.INFO,
    AdminActionId.SUSPEND_CUSTOMER: UiWarningLevel.CRITICAL,
    AdminActionId.UNSUSPEND_CUSTOMER: UiWarningLevel.ATTENTION,
    AdminActionId.RECHECK_EXCHANGE_CONNECTION: UiWarningLevel.INFO,
    AdminActionId.REVOKE_EXCHANGE_ACCESS: UiWarningLevel.CRITICAL,
    AdminActionId.RESET_TELEGRAM_LINK: UiWarningLevel.ATTENTION,
    AdminActionId.REVOKE_TELEGRAM_LIVE: UiWarningLevel.ATTENTION,
    AdminActionId.PUBLISH_PROMPT_VERSION: UiWarningLevel.ATTENTION,
    AdminActionId.ROLLBACK_PROMPT_VERSION: UiWarningLevel.CRITICAL,
    AdminActionId.GLOBAL_PAUSE_LIVE_TRADING: UiWarningLevel.CRITICAL,
    AdminActionId.GLOBAL_PAUSE_AI_RESPONSES: UiWarningLevel.CRITICAL,
    AdminActionId.GLOBAL_MAINTENANCE_MODE: UiWarningLevel.ATTENTION,
    AdminActionId.ADD_SUPPORT_NOTE: UiWarningLevel.INFO,
}


# Pflicht der Bestaetigung (und ggf. zweite Stufe)
ACTION_CONFIRMATION_TIER: dict[AdminActionId, ConfirmationTier] = {
    AdminActionId.TRIAL_EXTEND: ConfirmationTier.SINGLE_DIALOG,
    AdminActionId.TRIAL_STOP: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.GRANT_LIVE_TRADING: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.REVOKE_LIVE_TRADING: ConfirmationTier.TYPE_TO_CONFIRM,
    AdminActionId.PAUSE_CUSTOMER: ConfirmationTier.SINGLE_DIALOG,
    AdminActionId.RESUME_CUSTOMER: ConfirmationTier.SINGLE_DIALOG,
    AdminActionId.SUSPEND_CUSTOMER: ConfirmationTier.TYPE_TO_CONFIRM,
    AdminActionId.UNSUSPEND_CUSTOMER: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.RECHECK_EXCHANGE_CONNECTION: ConfirmationTier.NONE,
    AdminActionId.REVOKE_EXCHANGE_ACCESS: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.RESET_TELEGRAM_LINK: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.REVOKE_TELEGRAM_LIVE: ConfirmationTier.SINGLE_DIALOG,
    AdminActionId.PUBLISH_PROMPT_VERSION: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.ROLLBACK_PROMPT_VERSION: ConfirmationTier.TYPE_TO_CONFIRM,
    AdminActionId.GLOBAL_PAUSE_LIVE_TRADING: ConfirmationTier.TYPE_TO_CONFIRM,
    AdminActionId.GLOBAL_PAUSE_AI_RESPONSES: ConfirmationTier.TYPE_TO_CONFIRM,
    AdminActionId.GLOBAL_MAINTENANCE_MODE: ConfirmationTier.DOUBLE_CONFIRM,
    AdminActionId.ADD_SUPPORT_NOTE: ConfirmationTier.SINGLE_DIALOG,
}


@dataclass(frozen=True)
class AdminRouteDef:
    """Eine verwaltbare Seite: interner Schluessel, Pfad, deutscher Menue-Titel."""

    key: str
    path: str
    nav_label_de: str


# Hauptnavigation (Reihenfolge = empfohlene Sidebar)
ADMIN_PRIMARY_NAV: tuple[AdminRouteDef, ...] = (
    AdminRouteDef("start", "", "Start"),
    AdminRouteDef("customers", "/kunden", "Kunden"),
    AdminRouteDef("billing", "/vereinbarungen-zahlungen", "Vereinbarungen und Zahlungen"),
    AdminRouteDef("connections", "/anbindungen", "Anbindungen"),
    AdminRouteDef("ai", "/kuenstliche-intelligenz", "Kuenstliche Intelligenz"),
    AdminRouteDef("security", "/sicherheit-notfall", "Sicherheit und Notfall"),
    AdminRouteDef("reports", "/berichte", "Berichte"),
    AdminRouteDef("help", "/hilfe", "Hilfe"),
)


def admin_path(segment: str) -> str:
    """Haengt einen relativen Segment an die Basis (mit fuehrendem Slash segment)."""
    seg = segment if segment.startswith("/") else f"/{segment}"
    if seg == "/":
        return ADMIN_CONSOLE_BASE_PATH
    return f"{ADMIN_CONSOLE_BASE_PATH}{seg}"


def all_admin_nav_paths() -> tuple[str, ...]:
    """Vollstaendige Pfade fuer Router-Registrierung."""
    return tuple(admin_path(r.path) for r in ADMIN_PRIMARY_NAV)


# Kundendetail-Tabs (Unterseiten ohne eigene Top-Level-Nav)
class CustomerDetailTabId(str, Enum):
    OVERVIEW = "overview"
    TRIAL = "trial"
    CONTRACT = "contract"
    DEMO_LIVE = "demo_live"
    EXCHANGE = "exchange"
    TELEGRAM = "telegram"
    PAYMENTS = "payments"
    PROFIT_SHARE = "profit_share"
    AI_CUSTOMER = "ai_customer"
    SUPPORT_NOTES = "support_notes"
    HISTORY = "history"


CUSTOMER_DETAIL_TAB_LABELS_DE: dict[CustomerDetailTabId, str] = {
    CustomerDetailTabId.OVERVIEW: "Uebersicht",
    CustomerDetailTabId.TRIAL: "Probephase",
    CustomerDetailTabId.CONTRACT: "Vereinbarung und Freigaben",
    CustomerDetailTabId.DEMO_LIVE: "Uebung und Echtgeld",
    CustomerDetailTabId.EXCHANGE: "Boerse",
    CustomerDetailTabId.TELEGRAM: "Telegram",
    CustomerDetailTabId.PAYMENTS: "Zahlungen und Abo",
    CustomerDetailTabId.PROFIT_SHARE: "Beteiligung am Ergebnis",
    CustomerDetailTabId.AI_CUSTOMER: "KI fuer diesen Kunden",
    CustomerDetailTabId.SUPPORT_NOTES: "Unterstuetzung",
    CustomerDetailTabId.HISTORY: "Verlauf",
}


def customer_detail_path(customer_id: str, tab: CustomerDetailTabId | None = None) -> str:
    base = admin_path(f"/kunden/{customer_id}")
    if tab is None:
        return base
    return f"{base}/{tab.value}"


def super_admin_display_name_de() -> str:
    """Anzeigename des Voll-Admins fuer UI-Kopien ([FEST])."""
    return SUPER_ADMIN_CANONICAL_NAME


def requires_reason_note(action: AdminActionId) -> bool:
    """Ob eine Begruendung/Notiz Pflicht ist ([ANNAHME]: bei allen kritischen Aenderungen)."""
    return ACTION_WARNING_LEVEL[action] in (UiWarningLevel.ATTENTION, UiWarningLevel.CRITICAL)


def admin_console_descriptor() -> dict[str, str | int]:
    return {
        "admin_console_contract_version": ADMIN_CONSOLE_CONTRACT_VERSION,
        "admin_console_document_id": ADMIN_CONSOLE_DOCUMENT_ID,
        "base_path": ADMIN_CONSOLE_BASE_PATH,
        "super_admin_display_name": SUPER_ADMIN_CANONICAL_NAME,
        "primary_nav_entries": len(ADMIN_PRIMARY_NAV),
        "dashboard_kpis": len(DashboardKpiId),
        "admin_actions": len(AdminActionId),
    }


# Platzhalter-Komponente (fuer UI-Spezifikation)
EXPLAIN_PLACEHOLDER_SLOT_ID = "admin_explain_slot"
EXPLAIN_PLACEHOLDER_TITLE_DE = "Kurz erklaert"
EXPLAIN_PLACEHOLDER_BODY_DE = (
    "Hier kann spaeter ein Bild, ein Video oder eine gefuehrte Erklaerung eingebunden werden."
)
