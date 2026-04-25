# Main Console Execution Safety

Status: `implemented`

## Zielbild

Die Konsole `console/live-broker` zeigt den operativen Live-Broker- und Safety-Zustand fuer Philipp als einzigen Operator. Alle gefaehrlichen Aktionen sind fail-closed und laufen ohne sichere Endpoint-Verdrahtung niemals ausfuehrbar.

## Sichtbare Broker-/Safety-Elemente

- Broker-Uebersicht mit:
  - Betriebsmodus
  - Live-Trading aktiv (`ja`/`nein`/`blockiert`)
  - Bitget Public/Private Readiness
  - Reconcile-Status
  - Safety-Latch-Status
  - Kill-Switch-Status
  - letzte Order/Action
  - Unknown States
- Live-Blocker-Zeile mit klaren deutschen Gruenden:
  - `Safety-Latch aktiv`
  - `Kill-Switch aktiv`
  - `Reconcile nicht ok`
  - `Live-Runtime fehlt`
  - `Bitget Private Readiness gestoert`
- Safety Panel fuer Notfallpfade:
  - Kill-Switch armieren/freigeben
  - Safety-Latch freigeben
  - Cancel-All (kontrolliert)
  - Emergency-Flatten (reduce-only)

## Sicherheitsregeln in der UI

- Gefaehrliche Aktionen sind als Gefahr markiert und immer kontextgebunden.
- Jede Aktion oeffnet einen deutschen Bestaetigungsdialog mit Klartext.
- Ohne sicheren Endpoint bleibt die eigentliche Ausfuehrung deaktiviert.
- Bei aktiven Kill-Switch- oder Safety-Latch-Zustaenden bleiben normale Aktionen blockiert.
- Bei Reconcile-Fehler bleibt Live-Opening blockiert.

## Fehlende API/BFF-Verdrahtung

Folgende Endpunkte sind aktuell absichtlich als nicht verfuegbar markiert und fuehren deshalb zu deaktivierten Ausfuehrungsbuttons:

- `/api/dashboard/live-broker/kill-switch/arm`
- `/api/dashboard/live-broker/kill-switch/release`
- `/api/dashboard/live-broker/safety-latch/release`
- `/api/dashboard/live-broker/orders/cancel-all`
- `/api/dashboard/live-broker/emergency-flatten`

Damit wird keine Fake-Ausfuehrung eingebaut und keine echte Order ueber die UI ausgeloest.

## Relevante Implementierungsdateien

- `apps/dashboard/src/app/(operator)/console/live-broker/page.tsx`
- `apps/dashboard/src/components/safety/ExecutionSafetyPanel.tsx`
- `apps/dashboard/src/lib/live-broker-console.ts`
- `apps/dashboard/src/components/safety/__tests__/ExecutionSafetyPanel.test.tsx`
- `apps/dashboard/src/lib/__tests__/live-broker-console.test.ts`
