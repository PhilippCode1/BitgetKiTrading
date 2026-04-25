# Production Readiness Scorecard

## Ziel

Die Scorecard ist die zentrale Go/No-Go-Entscheidungszentrale fuer die private
Main Console von `bitget-btc-ai`. Philipp sieht damit, welcher Betriebsmodus
maximal verantwortbar ist und welche Live-Blocker offen sind.

## Modi

Bewertet werden `local_dev`, `paper`, `shadow`, `staging`,
`private_live_candidate`, `private_live_allowed` und `full_autonomous_live`.
Bei Unsicherheit wird immer der niedrigere Modus oder `NO_GO` gewaehlt.

## Entscheidungen

Moegliche Entscheidungen sind `GO`, `GO_WITH_WARNINGS`, `NO_GO`,
`NOT_ENOUGH_EVIDENCE` und `EXTERNAL_REQUIRED`.

## Datenfluss

`scripts/production_readiness_scorecard.py` liest
`docs/production_10_10/evidence_matrix.yaml`, erkennt vorhandene Reports unter
`reports/` und baut mit `shared_py.readiness_scorecard` ein reines
Main-Console-Datenmodell.

## Private-Live-Regel

`private_live_allowed` ist nur `GO`, wenn Bitget Readiness, Restore Test,
Shadow Burn-in, Safety Drill, Asset Universe, Asset Data Quality, Asset Risk
Tier, Live-Broker fail-closed, Reconcile, Kill-Switch/Safety-Latch und finaler
Owner-Signoff verified sind und keine Live-/Asset-Blocker offen bleiben.

`full_autonomous_live` bleibt standardmaessig `NO_GO`, bis alle relevanten
Kategorien verified sind und echte lange Live-Historie existiert.

## CLI

```bash
python scripts/production_readiness_scorecard.py --dry-run
python scripts/production_readiness_scorecard.py --output-md reports/production_readiness_scorecard.md
python scripts/production_readiness_scorecard.py --json
python scripts/production_readiness_scorecard.py --strict-live
```

## Reportfelder

Der Markdown-Report enthaelt Datum/Zeit, Git SHA, Projektname, Gesamtstatus,
Modusentscheidungen, Kategorieuebersicht, Live-Blocker, Asset-Blocker, fehlende
Evidence, naechste Schritte und Owner-Signoff-Feld.

## No-Go

Keine Scorecard darf `private_live_allowed` oder `full_autonomous_live` gruen
melden, solange P0-Blocker, fehlende Runtime-Reports oder fehlender Signoff
existieren. Billing-/Customer-Kategorien sind keine Pflicht fuer die private
Version.
