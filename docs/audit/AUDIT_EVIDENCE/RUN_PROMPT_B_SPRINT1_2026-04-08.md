# Prompt B — Sprint 1 (Iteration 2026-04-08)

## Ziele dieses Laufs

- `SPRINT_PLAN.md` auf 5 Sprints (Prompt-Vorgabe) ausgerichtet.
- E2E **Broken interactions** erweitert: feste kritische Konsole-Pfade + sichere Klicks (Terminal, Signale, Health).
- **Hydration-Bugfix:** `LiveDataSituationBar` verursachte React **#418** (SSR vs. Client `Date.now()`).
- Terminal: `data-testid="live-terminal-reload"` für stabile Tests.
- P0-3: Stack + `pnpm rc:health` auf diesem Host **grün** (Auszug unten).

## Befehle & Ergebnisse

| Befehl | Ergebnis |
|--------|----------|
| `pnpm check-types` | OK |
| `pnpm --filter @bitget-btc-ai/dashboard test -- --testPathPattern=live-data` | 3 passed |
| `docker compose ps` | Alle Kernservices `healthy` |
| `pnpm rc:health` | Exit 0 (warnings in system/health toleriert, siehe Script-Ausgabe) |
| `pnpm e2e -- e2e/tests/broken-interactions.spec.ts` (gegen **bestehendes** Dashboard-Image ohne Rebuild) | **FAIL** React #418 — **vor** Hydration-Fix reproduziert |

## E2E nach diesem Commit

Das laufende **Docker-Dashboard** enthält den Fix erst nach **`docker compose build dashboard` + `docker compose up -d dashboard`** (oder ein einzelner `next dev` auf der gleichen URL ohne zweite Instanz).

Erwartung: Keine `pageerror` mehr durch `LiveDataSituationBar`; Terminal-Test findet `live-terminal-reload` oder Fallback-Button-Label.

## P0-3 Auszug `rc:health` (2026-04-08)

```
OK  gateway /ready
OK  dashboard /api/health
OK  system-health ... warnings=['no_signals_timestamp', ...]
OK  rc_health_edge: alle Pruefungen gruen (warnings ... sind Hinweise, kein Fehler).
```
