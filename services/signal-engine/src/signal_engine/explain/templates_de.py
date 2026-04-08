from __future__ import annotations

# Template-basierte Kurztexte (deterministisch, nur Platzhalter aus Fakten)

SHORT_NEUTRAL = (
    "Neutral ({strength}/100) auf {tf}: keine klare Long/Short-Dominanz nach "
    "Struktur-, Momentum- und Multi-TF-Gates."
)
SHORT_LONG = (
    "Long bevorzugt ({strength}/100) auf {tf}: Aufwaertstrend in der Struktur "
    "mit gepruefter Konfluenz der Zeitrahmen."
)
SHORT_SHORT = (
    "Short bevorzugt ({strength}/100) auf {tf}: Abwaertstrend in der Struktur "
    "mit gepruefter Konfluenz der Zeitrahmen."
)

STOP_MARK = (
    "Stop triggert auf Mark Price (Bitget triggerType=mark_price; gegen Manipulation/"
    "Spikes robuster)."
)
STOP_FILL = (
    "Stop triggert auf Fill/Trade-Preis (reagiert schneller, aber noise-anfaelliger)."
)
STOP_UNKNOWN = (
    "Stop-Trigger-Typ ist in den Signalmetadaten nicht gesetzt; Default-Kontext siehe Konfiguration."
)
