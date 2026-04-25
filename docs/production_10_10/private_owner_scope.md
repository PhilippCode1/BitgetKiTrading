# Private Owner Scope

Diese Datei ist verbindlich fuer die weitere Produktausrichtung von
`bitget-btc-ai`. Sie ersetzt keine Sicherheits-, Trading- oder
Production-Readiness-Gates, sondern schraenkt den Produkt-Scope hart ein.

## Verbindliche Entscheidung

- Einziger Nutzer ist Philipp Crljic.
- Es gibt keine Kunden.
- Es gibt keine Mandanten.
- Es gibt kein Billing.
- Es gibt keinen Verkauf.
- Es gibt keine oeffentliche Launch-Zielsetzung.
- Es gibt keine Customer Journey als Produktziel.
- Es gibt keine Payment-, Subscription-, Tarif- oder Vertragsarchitektur als
  Zielarchitektur.

## Fokus

`bitget-btc-ai` dient der privaten institutionellen Eigen-Nutzung durch Philipp
Crljic. Der Fokus liegt auf Betrieb, Kontrolle, Asset-Analyse,
Entscheidungsnachvollziehbarkeit, Risk-Governance, deutscher Main Console,
Shadow-/Paper-Validierung und streng fail-closed behandelten Live-Gates.
Oeffentliche Launch-, Customer-Journey- oder Sales-Ziele sind ausdruecklich
out-of-scope.

## Konsequenzen fuer bestehende Artefakte

Vorhandene Customer-, Billing-, Commercial- oder Tenant-Artefakte duerfen nicht
blind geloescht werden, solange Code, Tests, Datenmodelle oder Gates davon
abhaengen. Sie sind zuerst zu inventarisieren und als `out-of-scope` oder
`deprecated` zu markieren. Danach duerfen sie kontrolliert konsolidiert,
abgesichert oder entfernt werden.

Keine spaetere Arbeit darf neue Verkaufs-, Kunden-, Payment- oder
Subscription-Flows als Ziel einbauen. Wenn solche Begriffe in Tests, Doku oder
Code noch auftauchen, sind sie als Legacy-Kontext zu behandeln, bis eine sichere
Migration abgeschlossen ist.

## Live-Geld-Auswirkung

Die private Ausrichtung reduziert keine Sicherheitsanforderung. Echte Bitget-
Orders bleiben blockiert, bis Asset-Freigabe, Datenqualitaet, Liquiditaet,
Bitget-Readiness, Risk-Governor, Shadow-/Safety-Evidence, Reconcile,
Kill-Switch-/Safety-Latch-Status und die explizite Owner-/Operator-Freigabe
durch Philipp nachweislich gruen sind.
