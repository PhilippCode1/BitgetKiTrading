# INCOMPLETE_PAGES — Abgleich mit Produktmatrix

Primärquelle im Repo: `PAGE_COMPLETION_MATRIX.md` (detaillierte Route-Tabelle + Fachschuld-Liste).

## Aus Matrix übernommene offene Punkte (nicht als „FAIL“ ohne Stack bewiesen, aber als UX-Schuld dokumentiert)

| Route / Bereich        | Befund (Kurz)                                      |
| ---------------------- | -------------------------------------------------- |
| `/console/paper`       | Teilweise hardcodiert Deutsch, i18n unvollständig  |
| `/console/news`        | `NewsTable` Spaltenköpfe noch Englisch             |
| `/console/strategies`  | `StrategiesTable` Köpfe teils Englisch            |
| `/console/account/*`   | Nicht alle Unterseiten Zeile-für-Zeile verifiziert |
| `/console/ops`         | Sehr dicht; Einsteiger-Zusammenfassung fehlt     |

## Verbesserungen (Audit 2026-04-07)

- `/console/market-universe` — **Daten-Lineage-Panel** (Stream, Broker, Reconcile, Kernsymbole) und Pagination; Matrix-Eintrag sollte aktualisiert werden.

## Update Prompt A Runde 4 (2026-04-07)

- **Arbeitsbaum (vor Commit):** `/console/terminal` und `/console/signals` — gleiche Health-Lineage wie Marktuniversum (`PlatformExecutionStreamsGrid`). Nach Merge: Matrix + `INCOMPLETE` hier bereinigen.

## Zusätzliche Routen (Matrix ggf. älter)

- `/console/diagnostics`, `/console/self-healing` — neuere Features; Matrix sollte erweitert werden.
- Forensic `/console/live-broker/forensic/[id]` — Stichprobe mit echtem Gateway nötig.

## Definition „blocked statt Placeholder“

Seite ist **OK**, wenn bei fehlendem Backend **explizit** Ursache + nächster Schritt (Link Health, Diagnose, edge-status) sichtbar sind — nicht nur leerer Main-Bereich.
