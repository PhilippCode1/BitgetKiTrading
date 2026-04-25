# Main Console Reports and Evidence

Status: `implemented`

## Zielbild

Die Main Console zeigt auf `console/reports` eine zentrale, deutsche Evidence- und Go/No-Go-Sicht. Sie behauptet keine Produktionsreife ohne Nachweis. Fehlende Reports bleiben fail-closed und blockieren Live.

## Evidence-Karten

- Shadow-Burn-in
- Bitget Readiness
- Restore-Test
- Safety Drill
- Alert Drill
- Performance/Backtest/Walk-forward
- Asset-Universum/Data Quality
- Production Scorecard
- Final Go/No-Go

Jede Karte zeigt:

- Status (`fehlt`, `teilweise`, `implementiert`, `verifiziert`, `extern erforderlich`)
- letzter Report (Pfad)
- Datum (Datei-MTime)
- Git SHA (falls im Runtime-Umfeld vorhanden)
- Live-Auswirkung
- nächster Schritt

## Fail-closed Verhalten

- Fehlt eine Report-Datei, wird die Karte auf `fehlt` gesetzt.
- Es gibt kein falsches `verifiziert`, wenn der Nachweis fehlt.
- Bei fehlendem Nachweis lautet die Auswirkung immer:
  `Nachweis fehlt, Live bleibt blockiert.`

## Datenquellen

- `docs/production_10_10/evidence_matrix.yaml` (Status und nächster Schritt je Kategorie)
- `reports/*` (Report-Dateien)

## Verlinkte Report-Generatoren

- `tools/check_10_10_evidence.py`
- `scripts/production_readiness_scorecard.py`

Hinweis: Die UI führt keine Scripts aus. Script-Ausführung bleibt ein expliziter, kontrollierter Operator-Schritt.

## Relevante Dateien

- `apps/dashboard/src/app/(operator)/console/reports/page.tsx`
- `apps/dashboard/src/app/(operator)/console/usage/page.tsx` (Legacy-Redirect)
- `apps/dashboard/src/lib/evidence-console.ts`
- `apps/dashboard/src/lib/__tests__/evidence-console.test.ts`
- `apps/dashboard/src/lib/main-console/navigation.ts`
