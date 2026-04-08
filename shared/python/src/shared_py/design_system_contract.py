"""
Designsystem: visuelle Tokens, Komponenten- und Sprachregeln (Modul Mate GmbH).

Bezug: docs/DESIGN_SYSTEM_MODUL_MATE.md (Prompt 9).

Zweck: stabile Schluessel fuer CSS-in-JS, Tailwind-Themes oder Design-Handoffs.
Werte sind Referenzen [ANNAHME] bis finale Markenfreigabe.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Final

DESIGN_SYSTEM_CONTRACT_VERSION = "1.0.0"
DESIGN_SYSTEM_DOCUMENT_ID = "DESIGN_SYSTEM_MODUL_MATE"

# --- Layout ---

CONTENT_MAX_WIDTH_PX: Final[int] = 1120
CONTENT_PADDING_X_PX: Final[int] = 24
SECTION_GAP_PX: Final[int] = 40

# --- Farben (HEX, ruhiges professionelles Set) ---

COLOR_SEMANTIC_HEX: Final[dict[str, str]] = {
    "canvas": "#F4F6F9",
    "surface": "#FFFFFF",
    "surface_muted": "#EEF1F6",
    "border": "#D8DEE6",
    "border_strong": "#B8C0CC",
    "text_primary": "#1A2332",
    "text_muted": "#5C6778",
    "text_on_primary": "#FFFFFF",
    "primary": "#2C5282",
    "primary_hover": "#234468",
    "success": "#2F6F4E",
    "warning": "#B45309",
    "danger": "#B42318",
    "info": "#2C5282",
    "focus_ring": "#4A7ABF",
}

# --- Abstaende (4-px-Basis) ---

SPACING_PX: Final[tuple[int, ...]] = (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)

# --- Radien ---

RADIUS_BUTTON_PX: Final[int] = 8
RADIUS_INPUT_PX: Final[int] = 8
RADIUS_CARD_PX: Final[int] = 12
RADIUS_CHIP_PX: Final[int] = 999

# --- Typografie ---

TYPOGRAPHY_FONT_STACK_CSS: Final[str] = (
    "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
)

TYPOGRAPHY_SIZE_BODY_PX: Final[int] = 16
TYPOGRAPHY_SIZE_SMALL_PX: Final[int] = 14
TYPOGRAPHY_SIZE_H1_PX: Final[int] = 28
TYPOGRAPHY_SIZE_H2_PX: Final[int] = 22
TYPOGRAPHY_SIZE_H3_PX: Final[int] = 18

# --- Interaktion ---

TOUCH_TARGET_MIN_PX: Final[int] = 44
FOCUS_OUTLINE_WIDTH_PX: Final[int] = 2

# --- Breakpoints (min-width) ---

BREAKPOINT_MIN_WIDTH_PX: Final[dict[str, int]] = {
    "sm": 480,
    "md": 768,
    "lg": 1024,
    "xl": 1280,
}

# --- Komponenten-Zahlen ---

CARD_PADDING_X_PX: Final[int] = 24
CARD_PADDING_Y_PX: Final[int] = 22
TABLE_ROW_HEIGHT_MIN_PX: Final[int] = 48
ELEVATION_CARD_CSS: Final[str] = "0 1px 3px rgba(26, 35, 50, 0.08), 0 1px 2px rgba(26, 35, 50, 0.06)"


class ButtonVariant(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    GHOST = "ghost"
    DANGER = "danger"


class SemanticStatusTone(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL = "neutral"


class AppSurfaceKind(str, Enum):
    """Gleiche Marke, unterschiedliche Layout-Dichte."""

    CUSTOMER = "customer"
    ADMIN = "admin"


def admin_uses_compact_tables_default() -> bool:
    """Admin: etwas kompaktere Tabellen erlaubt [ANNAHME]."""
    return True


# --- Medien-Platzhalter ---

MEDIA_PLACEHOLDER_ASPECT_RATIO: Final[str] = "16 / 9"
MEDIA_PLACEHOLDER_TITLE_DE: Final[str] = "Kurz erklaert"
MEDIA_PLACEHOLDER_CAPTION_DE: Final[str] = (
    "Hier erscheint spaeter ein Bild oder Video zu diesem Thema."
)

# --- UI-Zustaende: Schluessel fuer einheitliche Uebersetzungen ---

UI_STATE_COPY_KEYS_DE: Final[dict[str, str]] = {
    "empty_default_title": "Noch nichts hier",
    "empty_default_body": "Sobald Daten vorliegen, sehen Sie sie an dieser Stelle.",
    "empty_default_action": "Aktualisieren",
    "loading_title": "Wird geladen",
    "loading_body": "Einen Moment bitte.",
    "error_default_title": "Das hat nicht geklappt",
    "error_default_body": "Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.",
    "error_retry": "Erneut versuchen",
    "error_support": "Support kontaktieren",
    "success_default_title": "Erledigt",
    "success_default_body": "Ihre Aenderung wurde gespeichert.",
    "success_dismiss": "Schliessen",
}

# --- Darstellung fachlicher Bereiche (Kurzregeln fuer UI-Implementierung) ---

DISPLAY_RULE_CHART_LEGEND_DE: Final[str] = (
    "Achsen und Legende in Alltagssprache; keine internen Serien-IDs in Tooltips."
)
DISPLAY_RULE_KI_PANEL_DE: Final[str] = (
    "Ueberschrift z. B. Markteinordnung; keine Modellnamen oder Prompt-Begriffe in der Kopfzeile."
)
DISPLAY_RULE_ACCOUNT_MODE_DE: Final[str] = (
    "Modus Uebung oder Echtgeld immer sichtbar neben Kontext (Banner oder Chip)."
)
DISPLAY_RULE_PAYMENT_STATUS_DE: Final[str] = (
    "Status in Woertern: Bezahlt, Ausstehend, Fehlgeschlagen — keine englischen Enum-Werte."
)


# --- Begriffe, die Endnutzern nicht angezeigt werden duerfen [FEST UX] ---

FORBIDDEN_USER_VISIBLE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "api",
        "apis",
        "json",
        "jwt",
        "oauth",
        "sql",
        "http",
        "https",
        "endpoint",
        "stack trace",
        "stacktrace",
        "null",
        "undefined",
        "nan",
        "exception",
        "traceback",
        "uuid",
        "websocket",
        "graphql",
        "payload",
        "schema",
        "enum",
        "boolean",
        "varchar",
        "postgres",
        "redis",
        "kafka",
        "kubernetes",
        "docker",
        "git",
        "commit",
        "deploy",
        "build",
        "lint",
        "token",
        "bearer",
        "header",
        "500",
        "404",
        "403",
        "401",
        "prompt",
        "gpt",
        "llm",
        "embedding",
        "vector",
        "latency",
        "timeout ms",
        "stack",
        "heap",
        "debug",
        "verbose",
    }
)


def copy_may_contain_forbidden_term(text: str) -> bool:
    """
    True, wenn der Text fuer Endnutzer ungeeignete technische Woerter enthaelt (heuristisch).

    Prueft ganze Woerter / Phrasen mit Wortgrenzen, um False Positives in normalen Woertern
    zu vermeiden.
    """
    lower = text.lower()
    for term in FORBIDDEN_USER_VISIBLE_TERMS:
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            return True
    return False


def design_system_descriptor() -> dict[str, str | int]:
    return {
        "design_system_contract_version": DESIGN_SYSTEM_CONTRACT_VERSION,
        "design_system_document_id": DESIGN_SYSTEM_DOCUMENT_ID,
        "content_max_width_px": CONTENT_MAX_WIDTH_PX,
        "semantic_colors": len(COLOR_SEMANTIC_HEX),
        "forbidden_term_count": len(FORBIDDEN_USER_VISIBLE_TERMS),
        "breakpoint_keys": len(BREAKPOINT_MIN_WIDTH_PX),
    }
