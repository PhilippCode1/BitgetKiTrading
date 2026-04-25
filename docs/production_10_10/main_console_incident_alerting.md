# Main Console: Incidents, Alerts und Eskalation (Deutsch)

## Zweck

Philipp Crljic betreibt `bitget-btc-ai` allein als Owner und Operator. Technische Health-Warnungen, Reconcile-Status und Broker-Flags müssen in **verständliche, priorisierte deutsche Meldungen** übersetzt werden — ohne falsche Entwarnung, ohne Secrets und ohne Anlageberatung.

## Severity-Stufen

| Stufe | Bedeutung |
|-------|-----------|
| **P0** | Sofortiger Live-Blocker; echtes Geld oder Systemkontrolle potenziell gefährdet. |
| **P1** | Kritische Störung; Live bleibt blockiert oder stark eingeschränkt. |
| **P2** | Warnung; Beobachtung und geplante Maßnahme. |
| **P3** | Hinweis; kein akuter Eingriff. |

Unbekannte oder fehlende Severity wird **fail-safe als P1** behandelt (`normalize_severity` in `shared/python/src/shared_py/operator_alerts.py`).

## P0-Zustände (Live blockiert)

Mindestens P0 mit `live_blockiert=true`, wenn:

1. Reconcile fehlgeschlagen.
2. Exchange-Truth fehlt oder ist unklar.
3. Kill-Switch aktiv.
4. Safety-Latch aktiv.
5. Bitget private API: Auth-Fehler.
6. Redis/DB im livekritischen Pfad ausgefallen.
7. Asset-Datenqualität FAIL bei livefähigem Asset.
8. Liquiditäts-Guard blockiert wegen fehlendem Orderbuch.
9. Unbekannter Order-Status nach Submit.
10. Secret-Leak-Verdacht.
11. Produktion mit unsicherer ENV-Konfiguration.
12. Live-Flags aktiv ohne Owner-Freigabe.

Konkrete Fabrik-Funktionen: `operator_alerts.py` (`alert_from_reconcile_fail`, …).

## Pflichtfelder pro Meldung (Contract)

Jede normalisierte Meldung enthält:

- `titel_de`
- `beschreibung_de`
- `severity` (P0–P3)
- `live_blockiert` (bool; bei P0 immer gesetzt und in der UI erklärt)
- `betroffene_komponente`
- `betroffene_assets` (Liste, leer erlaubt)
- `empfohlene_aktion_de`
- `nächster_sicherer_schritt_de`
- `technische_details_redacted` (keine Secrets)
- `zeitpunkt` (ISO UTC)
- `korrelation_id` (UUID)
- `aktiv` (true = aktuell; false = historisch / archiviert)

## UI-Regeln

1. P0 darf **nie** grün oder neutral dargestellt werden.
2. Fehlende Daten dürfen **nicht** als „OK“ erscheinen (explizit „unbekannt“ / „keine Daten“).
3. Sortierung: **höchste Kritikalität zuerst**; **aktive** Alerts vor **historischen** (`sort_operator_alerts`).
4. Keine Billing-, Kunden-, Abo- oder SaaS-Begriffe in Operator-Texten.

## Implementierung

| Bereich | Ort |
|---------|-----|
| Normalisierung (Python, Tests) | `shared/python/src/shared_py/operator_alerts.py` |
| Main Console Ansicht | `apps/dashboard/src/app/(operator)/console/incidents/page.tsx` |
| View-Model (Health + Live-Broker Snapshot) | `apps/dashboard/src/lib/operator-alerts-view-model.ts` |
| Release-Check | `tools/check_main_console_incidents.py` |

## Echte Alert-Quellen (Anbindung)

Die Seite **Vorfälle & Warnungen** baut aktuell aus **Gateway-Health** und **Live-Broker-Runtime** (bestehende BFF-/Fetch-Pfade). Weitere Quellen sollten dieselbe Normalisierung nutzen:

- Alert-Engine / Monitor-Outbox (Gateway `ops_summary`)
- Risk-Governor / Datenqualitäts-Gates (Reports oder API)
- Audit-Stream (kritische Ereignisse)

Bis zur vollständigen Backend-Anbindung bleibt die Darstellung **fail-closed**: fehlende Daten = keine grüne „Alles OK“-Fläche für P0-relevante Bereiche.

## Verweise

- `docs/production_10_10/main_console_safety_command_center.md`
- `docs/production_10_10/main_console_product_direction.md`
