# Sprint 2b — Terminal & Signale: gleiche Health-Lineage wie Marktuniversum

**Datum:** 2026-04-07  
**Ziel:** P1-6 / Sprint-2-Transparenz — auf `/console/terminal` und `/console/signals` dieselbe Plattform-Sicht (Execution-Modus, LIVE/SHADOW/PAPER, letzte Kerze/Signal, market-stream, live-broker, Reconcile) wie im Marktuniversum-Panel.

## Umsetzung

- Neue Server-Komponente: `apps/dashboard/src/components/console/PlatformExecutionStreamsGrid.tsx` (`variant`: `card` | `bare`).
- `MarketUniverseDataLineagePanel` nutzt `variant="bare"` (kein doppeltes Panel).
- Terminal: `PlatformExecutionStreamsGrid` mit `data-testid="platform-execution-lineage-terminal"`.
- Signale: `data-testid="platform-execution-lineage-signals"`.
- i18n: `live.platformLineage.*` in `de.json` / `en.json`.
- E2E: `e2e/tests/release-gate.spec.ts` — Assertions für beide testids.

## Tests (lokal auszuführen)

```bash
pnpm --filter @bitget-btc-ai/dashboard run check-types
pnpm --filter @bitget-btc-ai/dashboard test
# Mit laufendem Stack + E2E_BASE_URL:
pnpm e2e -- e2e/tests/release-gate.spec.ts
```

## Offen

- P1-4 Lastprofil Marktuniversum.
- P1-6 vollständig: Ribbon vs. Bar — nur wenn Konflikte zwischen Quellen auftreten, explizit dokumentieren.
