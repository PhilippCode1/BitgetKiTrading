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

## No-Go-Regeln

Wenn Kill-Switch oder Safety-Latch eine Opening Order nicht blockieren, ist der
Drill `FAIL`. Emergency-Flatten darf nur safe/reduce-only sein.

## Philipp liest den Report

Philipp prueft `Go/No-Go`, `Opening Order blockiert`,
`Emergency-Flatten reduce-only` und `Live-Write erlaubt`. Ohne archivierten
Safety-Drill bleibt echtes Live blockiert.
