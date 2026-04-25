# AGENTS.md - verbindliche Codex-Arbeitsgrundlage

Dieses Repository heisst verbindlich `bitget-btc-ai`. Cursor arbeitet immer auf
diesem Projektnamen, auch wenn Remote- oder Altbezeichnungen abweichen. Es
bereitet eine private, deutsche, institutionell kontrollierte Bitget-Multi-Asset
KI-Trading-Anwendung fuer Philipp Crljic vor. Es darf niemals ohne gepruefte
Gates echtes Geld handeln.

Echte Produktionsreife bedeutet: Code, Tests, Betrieb, Security, Recovery,
Compliance, Monitoring, deutsche Main Console, Owner-Freigaben und Signoff sind
nachweislich vorhanden. Eine Behauptung ohne Evidence ist kein
Produktionsnachweis.

## Projektziel

`bitget-btc-ai` soll eine private Main-Console-Plattform fuer Philipp Crljic
werden:

- Paper-, Shadow- und Live-Modi sind hart getrennt.
- Live-Trading ist immer explizit, operatorisch freigegeben und fail-closed.
- Risk-Governor, Live-Broker, Exchange-Control, Asset-/Datenqualitaets-/
  Liquiditaets-/Owner-Gates, Kill-Switch, Safety-Latch, Reconcile und
  Audit-Trail duerfen nicht umgangen werden.
- API-Keys, Secrets, private Betriebsdaten und Owner-Freigaben sind geschuetzt.
- Die Benutzeroberflaeche ist deutsch und wird auf eine zentrale Main Console
  ausgerichtet.
- Multi-Asset-Bitget-Faehigkeit wird aufgebaut; Live-Trading bleibt auch fuer
  jedes neue Asset fail-closed.
- Production-Readiness wird ueber Tests, Doku, Runbooks, Evidence und externe
  Signoffs bewiesen.

## Verbindliche private Produktausrichtung

- Es gibt nur einen Hauptnutzer: Philipp Crljic.
- Philipp ist alleiniger Admin, Operator und Owner.
- Die Anwendung wird nicht verkauft.
- Billing, Customer-Flows, Subscriptions, Tarife, Vertragsverwaltung,
  Payment-Flows, oeffentliche Marketing-Strecken und Multi-Tenant-Ziele sind
  nicht mehr Produktziel.
- Bestehende Billing-, Customer-, Commercial- oder Tenant-Artefakte duerfen nur
  als Legacy-/Out-of-scope-Abhaengigkeiten erhalten, abgesichert oder geordnet
  entfernt werden. Cursor darf sie nicht als neue Zielrichtung ausbauen.
- Alle UI-Texte der finalen Anwendung muessen deutsch sein.
- Die Main Console ist die zentrale Oberflaeche fuer Status, Assets, Signale,
  Risk, Live-Broker, KI-Erklaerung, Reports, Alerts, Settings und Go/No-Go.
- Cursor darf keine echten Secrets erzeugen, anzeigen, loggen oder speichern.
- Cursor darf keine echten Bitget-Orders ausloesen.
- Cursor darf niemals behaupten, `10/10` sei erreicht, wenn Evidence fehlt.

## Cursor-Arbeitsmodus

Die folgenden Regeln gelten fuer Cursor verbindlich. "Codex" und "Cursor" sind
im Repo-Kontext gleichbedeutend, wobei die operative Verantwortung bei Cursor
liegt.

Cursor muss immer in dieser Reihenfolge arbeiten:

1. Repository lesen und relevante Dateien finden, bevor Aenderungen gemacht werden.
2. Problem verstehen.
3. Trading-, Risk-, Security-, Owner-, Compliance- und Betriebsrisiken erkennen.
4. Plan erstellen, sofern die Aufgabe nicht trivial ist.
5. Minimal-invasive Aenderungen machen.
6. Passende Tests ergaenzen oder aktualisieren.
7. Tests und Checks ausfuehren.
8. Fehler analysieren, korrigieren und erneut pruefen.
9. Doku, ENV-Referenzen, Runbooks oder Evidence aktualisieren.
10. Evidence-Zusammenfassung liefern.

Bei bestehenden ungecommitteten Aenderungen gilt: nicht zuruecksetzen, nicht
ueberschreiben und nicht bereinigen, ausser der Nutzer verlangt es explizit.

## Pflicht zur Selbstpruefung

Codex darf eine Aufgabe nicht als fertig melden, wenn:

- Tests fehlen, obwohl Verhalten geaendert wurde.
- Relevante Tests fehlschlagen.
- Doku nicht aktualisiert wurde.
- ENV-Aenderungen nicht dokumentiert wurden.
- Risk-, Trading-, Live-Broker-, Owner- oder Legacy-Billing-/Tenant-Auswirkungen nicht
  bewertet wurden.
- Eine neue Live-Gefahr entstanden ist.
- Secrets versehentlich exponiert werden koennten.
- Die Aenderung nicht verifiziert wurde.
- Evidence oder Restrisiko nicht klar berichtet wurde.

Wenn ein Check wegen fehlender lokaler Umgebung scheitert, muss Codex den
exakten Befehl, die Ursache und die Einordnung als echter Blocker oder externer
Blocker dokumentieren.

## Keine echten Secrets

Codex darf niemals echte API-Keys, Passwoerter, Tokens, Exchange-Secrets,
OpenAI-Keys, Bitget-Keys, Telegram-Tokens, DB-Passwoerter, Redis-Passwoerter,
JWT-Secrets, Admin-Tokens, Wallet-Daten oder Kundendaten erzeugen, speichern,
ausgeben, loggen oder committen.

Erlaubt sind nur eindeutig synthetische Platzhalter wie
`CHANGE_ME_IN_SECRET_STORE`, `example-only` oder dokumentierte Dummy-Werte.

## Kein echter Live-Trade durch Default

Codex darf keine Aenderung einbauen, die standardmaessig echte Orders
ermoeglicht. Live-Trading muss immer an harte Gates gebunden sein:

- `EXECUTION_MODE=live`
- `LIVE_TRADE_ENABLE=true`
- `LIVE_BROKER_ENABLED=true`
- Operator-Release
- Shadow-Match
- Exchange-Health
- Risk-Governor-Freigabe
- Asset-, Datenqualitaets-, Liquiditaets- und Owner-Gates
- Kill-Switch nicht aktiv
- Safety-Latch nicht aktiv
- keine ungeklaerte Reconcile-Lage

Jede neue Trading-Funktion muss beweisen, dass Paper/Shadow der Default bleibt
und Live ohne vollstaendige Gates blockiert.

## Fail-Closed-Regel

Bei jedem Zweifel muss das System blockieren. Fail-closed gilt besonders bei:

- fehlendem Redis
- fehlender DB
- fehlender Exchange-Truth
- fehlendem Operator-Release
- fehlendem Shadow-Match
- fehlendem Instrumentenkatalog
- fehlendem Risk-Kontext
- fehlender Owner-/Operator-Freigabe durch Philipp
- Provider-Fehlern
- Stale-Daten
- Reconcile-Divergenz
- Kill-Switch
- Safety-Latch
- unklarer Auth-/RBAC-Lage
- unklaren Legacy-Billing-, Customer- oder Tenant-Abhaengigkeiten

Unsichere Defaults sind Fehler. Fallbacks duerfen niemals echte Orders
beguenstigen.

## Dokumentationspflicht

Jede Aenderung an diesen Bereichen muss passende Doku aktualisieren:

- Runtime
- ENV
- API
- Gateway
- Risk
- Trading
- Live-Broker
- Legacy-Billing-/Customer-/Tenant-Abhaengigkeiten
- Dashboard
- Operator-UI
- Main Console
- Legacy-Kunden-UI
- Security
- CI
- Deployment
- Recovery
- Monitoring
- Compliance
- Release-Prozess

Relevante Referenzorte sind unter anderem `README.md`, `docs/LaunchChecklist.md`,
`docs/ci_release_gates.md`, `docs/compose_runtime.md`,
`docs/recovery_runbook.md`, `docs/SECRETS_MATRIX.md`,
`docs/shadow_burn_in_ramp.md`, `docs/production_10_10/*` und service-nahe
READMEs.

## Testpflicht

Codex muss passende Tests ergaenzen oder aktualisieren. Tests muessen reales
Verhalten pruefen, nicht nur Dateiexistenz.

Je nach Aenderung sind mindestens relevant:

- Python Unit-/Integrationstests unter `tests/`.
- Dashboard/Jest/E2E-Tests unter `apps/dashboard` und `e2e`.
- Release-/Security-Gates unter `tools/`.
- ENV-Validatoren fuer geaenderte Profile.
- Fail-closed-Tests fuer Live-Broker, Risk, Redis, DB, Reconcile, Asset-,
  Datenqualitaets-, Liquiditaets- und Owner-Gates.
- Doku-/Format-Checks, wenn Markdown, YAML, JSON oder UI-Texte geaendert
  wurden.

Wenn ein Test nicht ausgefuehrt werden kann, muss Codex den Grund nennen und
einen konkreten Nachholpfad angeben.

## Evidence-Pflicht

Am Ende jeder Aufgabe muss Codex berichten:

- geaenderte Dateien
- ausgefuehrte Befehle
- Testergebnisse
- Fehler und Korrekturen
- verbleibende Risiken
- ob Live-Geld weiterhin blockiert ist
- welcher naechste Schritt logisch folgt

Evidence darf keine Secrets enthalten. Logs muessen vor Weitergabe auf
Secret-Leaks geprueft werden.

## Keine Marketing-Sprache

Codex darf niemals schreiben: "10/10 erreicht", wenn Nachweise fehlen.

Erlaubte Statuswerte sind nur:

- `implemented`
- `partial`
- `verified`
- `external_required`
- `missing`

Jede Production-Aussage muss zwischen Repo-Nachweis und externer Abnahme
trennen.

## Zentrale Production-Readiness-Dokumente

Vor riskanten Aenderungen muessen diese Dateien beachtet werden:

- `docs/production_10_10/README.md`
- `docs/production_10_10/private_owner_scope.md`
- `docs/production_10_10/main_console_product_direction.md`
- `docs/production_10_10/cursor_work_protocol.md`
- `docs/production_10_10/10_10_definition.md`
- `docs/production_10_10/evidence_matrix.md`
- `docs/production_10_10/codex_work_protocol.md`
- `docs/production_10_10/no_go_rules.md`
- `docs/production_10_10/00_master_gap_register.md`
- `docs/production_10_10/evidence_registry.md`

Diese Dateien sind die verbindliche Grundlage fuer Codex-Arbeit im Repo.
