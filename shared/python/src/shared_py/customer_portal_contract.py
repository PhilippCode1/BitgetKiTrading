"""
Kundenportal: Routen, Navigation und nutzerfreundliche Texte (Modul Mate GmbH).

Bezug: docs/CUSTOMER_PORTAL_MODUL_MATE.md (Prompt 6).

Alle oeffentlichen Beschriftungen sind bewusst **ohne Techniksprache**.
Locale: derzeit Deutsch (`*_DE`); gleiche Schluessel ermoeglichen spaeter Uebersetzungen.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

CUSTOMER_PORTAL_CONTRACT_VERSION = "1.0.0"
CUSTOMER_PORTAL_DOCUMENT_ID = "CUSTOMER_PORTAL_MODUL_MATE"

# Kurzer, international brauchbarer Pfad [ANNAHME]
CUSTOMER_PORTAL_BASE_PATH: Final[str] = "/app"


class CustomerPortalPageId(str, Enum):
    """Stabile IDs fuer Router, Analytics und Tests."""

    HOME = "home"
    MARKET = "market"
    PRACTICE = "practice"
    LIVE = "live"
    ORDERS = "orders"
    HISTORY = "history"
    SUBSCRIPTION = "subscription"
    AGREEMENT = "agreement"
    TELEGRAM = "telegram"
    SETTINGS = "settings"
    HELP = "help"


class SubscriptionIntervalId(str, Enum):
    """Abrechnungsintervalle fuer klare Darstellung."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


SUBSCRIPTION_INTERVAL_LABELS_DE: dict[SubscriptionIntervalId, str] = {
    SubscriptionIntervalId.DAY: "Taeglich",
    SubscriptionIntervalId.WEEK: "Woechentlich",
    SubscriptionIntervalId.MONTH: "Monatlich",
    SubscriptionIntervalId.YEAR: "Jaehrlich",
}


def subscription_billing_explanation_de(interval: SubscriptionIntervalId) -> str:
    """Ein Satz, wann abgerechnet wird — ohne Kleingedrucktes-Stil."""
    return {
        SubscriptionIntervalId.DAY: "Ihr Plan wird jeden Tag zum gleichen Zeitpunkt verlaengert.",
        SubscriptionIntervalId.WEEK: "Ihr Plan wird jede Woche zum gleichen Wochentag verlaengert.",
        SubscriptionIntervalId.MONTH: "Ihr Plan wird jeden Monat zum gleichen Kalendertag verlaengert.",
        SubscriptionIntervalId.YEAR: "Ihr Plan wird einmal pro Jahr verlaengert.",
    }[interval]


@dataclass(frozen=True)
class CustomerNavItem:
    page_id: CustomerPortalPageId
    path_segment: str
    label_de: str
    description_de: str


CUSTOMER_PRIMARY_NAV: tuple[CustomerNavItem, ...] = (
    CustomerNavItem(
        CustomerPortalPageId.HOME,
        "",
        "Uebersicht",
        "Ihr aktueller Stand, naechste Schritte und Modus.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.MARKET,
        "markt",
        "Markt und Einordnung",
        "Charts, Signale und verstaendliche Bewertung — ohne technische Details.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.PRACTICE,
        "uebung",
        "Uebungskonto",
        "Alles mit virtuellem Geld. Ideal zum Kennenlernen.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.LIVE,
        "echtgeld",
        "Echtgeldkonto",
        "Echte Boersenauftraege — nur wenn freigegeben.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.ORDERS,
        "orders",
        "Auftraege",
        "Ihre Orders, klar getrennt nach Uebung und Echtgeld.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.HISTORY,
        "verlauf",
        "Verlauf",
        "Was wann passiert ist — nachvollziehbar erzaehlt.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.SUBSCRIPTION,
        "abo",
        "Abo und Zahlungen",
        "Plan, Laufzeit, Rechnungen.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.AGREEMENT,
        "vereinbarung",
        "Vereinbarung und Freigabe",
        "Status Ihrer Vereinbarung und was fuer Echtgeld noetig ist.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.TELEGRAM,
        "telegram",
        "Telegram",
        "Benachrichtigungen verbinden und Rechte pruefen.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.SETTINGS,
        "einstellungen",
        "Einstellungen",
        "Profil, Sicherheit und Benachrichtigungen.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.HELP,
        "hilfe",
        "Hilfe und Support",
        "Antworten, Kontakt und kurze Erklaerungen.",
    ),
)


def customer_portal_path(segment: str) -> str:
    if not segment:
        return CUSTOMER_PORTAL_BASE_PATH
    seg = segment if segment.startswith("/") else f"/{segment}"
    return f"{CUSTOMER_PORTAL_BASE_PATH}{seg}"


def all_customer_portal_nav_paths() -> tuple[str, ...]:
    return tuple(customer_portal_path(item.path_segment) for item in CUSTOMER_PRIMARY_NAV)


# --- Modus-Banner (immer sichtbar wenn relevant) ---

MODE_BANNER_TRIAL_DE = (
    "Sie sind in der Probephase. Alles laeuft als Uebung — es wird kein echtes Geld bewegt."
)
MODE_BANNER_PRACTICE_ONLY_DE = "Sie sind im Uebungsmodus. Es wird kein echtes Geld bewegt."
MODE_BANNER_LIVE_DE = (
    "Sie sind im Echtgeldmodus. Echte Marktpreise und echtes Geld — Verluste sind moeglich."
)
MODE_BANNER_LIVE_LOCKED_DE = (
    "Der Echtgeldmodus ist noch nicht freigegeben. Hier sehen Sie, was als Naechstes noetig ist."
)


# --- Vertrauen / Footer / kurze Hilfen ---

TRUST_COPY_DE: dict[str, str] = {
    "footer_risk": "Trading birgt Risiken. Nur nutzen, was Sie sich leisten koennen.",
    "footer_data": "Ihre Daten werden geschuetzt und nur fuer den vereinbarten Zweck genutzt.",
    "encrypted_connection": "Ihre Verbindung ist verschluesselt.",
    "two_factor_hint": "Erhoehen Sie die Sicherheit mit einer zweiten Bestaetigung beim Login.",
    "explain_slot_title": "Kurz erklaert",
    "explain_slot_body": "Hier finden Sie spaeter ein kurzes Video oder eine einfache Grafik zu diesem Thema.",
}


# --- Haeufige Buttons (einheitlich) ---

BUTTON_LABELS_DE: dict[str, str] = {
    "continue": "Weiter",
    "back": "Zurueck",
    "save": "Speichern",
    "understood": "Verstanden",
    "download_invoice": "Rechnung herunterladen",
    "contact_support": "Support kontaktieren",
    "start_practice": "Uebung starten",
    "view_agreement": "Vereinbarung ansehen",
    "refresh_status": "Status aktualisieren",
}


# --- Statuszeile (Kurztexte fuer globale Anzeige) ---

STATUS_LINE_PREFIX_DE = "Ihr Stand:"


def status_mode_label_de(*, practice_active: bool, live_active: bool) -> str:
    if live_active:
        return "Modus: Echtgeld"
    if practice_active:
        return "Modus: Uebung"
    return "Modus: eingeschraenkt"


# --- UX: explizit verbotene Muster (Design/QA) ---

FORBIDDEN_UX_PATTERNS: tuple[str, ...] = (
    "Echten und virtuellen Handel ohne klare visuelle Trennung zeigen.",
    "Den aktiven Modus nur in kleinem Grautext verstecken.",
    "Fehlermeldungen mit technischen Codes oder Feldnamen an Endnutzer ausgeben.",
    "Echtgeldaktionen ohne zusaetzliche Bestaetigung erlauben.",
    "Leere oder sperrende Seiten ohne Erklaerung und ohne naechsten Schritt.",
    "Rechnungen und Handelsaktivitaeten ohne erkennbare Ueberschriften mischen.",
    "Preise oder Abo-Intervalle erst nach Kauf vollstaendig offenlegen.",
)


def customer_portal_descriptor() -> dict[str, str | int]:
    return {
        "customer_portal_contract_version": CUSTOMER_PORTAL_CONTRACT_VERSION,
        "customer_portal_document_id": CUSTOMER_PORTAL_DOCUMENT_ID,
        "base_path": CUSTOMER_PORTAL_BASE_PATH,
        "nav_entries": len(CUSTOMER_PRIMARY_NAV),
        "forbidden_ux_pattern_count": len(FORBIDDEN_UX_PATTERNS),
    }


def page_public_title_de(page_id: CustomerPortalPageId) -> str:
    """Ueberschrift fuer die Seite (H1-Niveau)."""
    for item in CUSTOMER_PRIMARY_NAV:
        if item.page_id == page_id:
            return item.label_de
    raise KeyError(page_id)
