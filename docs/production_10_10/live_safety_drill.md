# Live Safety Drill

## Warum Pflicht

Kill-Switch, Safety-Latch und Emergency-Flatten muessen vor Live messbar
beweisen, dass Opening Orders blockiert und Notfallaktionen sicher/reduce-only
bleiben.

## Sicherer Lauf

`scripts/live_safety_drill.py --dry-run` und `--mode simulated` simulieren die
Safety-Lage ohne externe Systeme. Es wird keine Exchange-Verbindung aufgebaut.

## Keine echten Orders

Das Tool erzeugt ausschliesslich simulierte Evidence. Es enthaelt keine
Submit-/Cancel-/Replace- oder Bitget-Write-Funktion.

## Reportfelder

Der Report enthaelt Datum/Zeit, Git-SHA, Modus, Kill-Switch aktiv,
Safety-Latch aktiv, Opening Order blockiert, Emergency-Flatten reduce-only,
Audit erwartet, Alert erwartet, Go/No-Go und Live-Write erlaubt.

## Externer Drill-Contract

Die Simulation ist Code-Evidence, aber keine Live-Freigabe. Fuer private
Live-Evidence muss ein echter Staging-/Shadow-Drill als secret-freies JSON
gegen den Contract geprueft werden:

```bash
python scripts/live_safety_drill.py \
  --evidence-json docs/production_10_10/live_safety_drill.template.json \
  --strict \
  --output-md reports/live_safety_drill.md \
  --output-json reports/live_safety_drill.json
```

Das Repo-Template bleibt absichtlich `FAIL`, bis echte Evidence vorliegt. Fuer
Live muss mindestens belegt sein:

- Drill-Start/-Ende, Git-SHA, Operator und Evidence-Referenz
- Kill-Switch arm verifiziert
- Kill-Switch blockiert Opening-Submit
- Kill-Switch-Release ist operatorisch gegated
- Safety-Latch arm verifiziert
- Safety-Latch blockiert Submit und Replace
- Safety-Latch-Release verlangt Begruendung
- Emergency-Flatten getestet
- Emergency-Flatten ist reduce-only
- Exchange-Truth wurde vor Flatten geprueft
- Flatten kann Exposure nicht erhoehen
- Cancel-All getestet
- Audit-Trail verifiziert
- Alert-Zustellung verifiziert
- Main-Console-Safety-State verifiziert
- Reconcile nach Drill ist `ok`
- waehrend Drill war `live_write_allowed_during_drill=false`
- `real_exchange_order_sent=false`
- Owner-Signoff separat vorhanden

Felder mit Secret-Bezug wie `database_url`, `dsn`, `password`, `secret`,
`token`, `api_key`, `private_key` oder `authorization` duerfen keine echten Werte
enthalten.

## No-Go-Regeln

Wenn Kill-Switch oder Safety-Latch eine Opening Order nicht blockieren, ist der
Drill `FAIL`. Emergency-Flatten darf nur safe/reduce-only sein.

## Philipp liest den Report

Philipp prueft `Go/No-Go`, `Opening Order blockiert`,
`Emergency-Flatten reduce-only` und `Live-Write erlaubt`. Ohne archivierten
Safety-Drill bleibt echtes Live blockiert.
