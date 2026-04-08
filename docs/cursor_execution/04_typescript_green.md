# TypeScript grün (Dashboard + shared-ts)

Stand: 2026-04-05

## Ziel

`pnpm check-types` und `pnpm --dir apps/dashboard run check-types` ohne Fehler; Typen an reale Gateway-JSON-Verträge gebunden, keine `any`-/`unknown`-Workarounds für diese Brüche.

## Behobene Typbrüche

### 1. Admin-Hub: `SystemHealthResponse` ohne `status` / `overall`

- **Ursache:** `healthOk` in `admin/page.tsx` prüfte `h?.status` und einen Cast auf `overall?.ok`. Der Endpoint `GET /v1/system/health` liefert weder `status` noch `overall` auf Top-Level; die Payload kommt aus `compute_system_health_payload()` mit `database`, `warnings`, … (siehe `services/api-gateway/src/api_gateway/routes_system_health.py`).
- **Geänderte Dateien:** `apps/dashboard/src/lib/health-service-reachability.ts` (neu: `systemHealthAdminHubGreen`), `apps/dashboard/src/app/(operator)/console/admin/page.tsx`, `apps/dashboard/src/lib/__tests__/health-service-reachability.test.ts`.
- **Warum der Fix passt:** Grün genau dann, wenn `database === "ok"` und `warnings` ein leeres Array ist — das spiegelt den vom Gateway gebauten Zustand (kein Schema-/Stale-/Ops-Code in `warnings`) wider, ohne nicht existierende Felder zu erfinden. **Hinweis:** Die alte `healthOk`-Logik griff auf nie gelieferte Felder zu und lieferte damit praktisch immer „Prüfen“; die neue Logik entspricht der echten JSON-Struktur.

### 2. Paper-Seite: `account_ledger_recent` optional vs. lokaler Pflicht-Typ

- **Ursache:** `metrics` wurde als Objekt mit **Pflichtfeld** `account_ledger_recent: PaperLedgerEntry[]` inferiert. `fetchPaperMetricsSummary()` liefert `PaperMetricsResponse`, wo `account_ledger_recent` **optional** ist (`GatewayReadEnvelope & { … account_ledger_recent?: … }`). Beim Zuweisen aus `Promise.all` entstand TS2322.
- **Geänderte Dateien:** `apps/dashboard/src/lib/paper-metrics-defaults.ts` (neu: `emptyPaperMetricsResponse`), `apps/dashboard/src/app/(operator)/console/paper/page.tsx`, `apps/dashboard/src/lib/__tests__/paper-metrics-defaults.test.ts`.
- **Warum der Fix passt:** Der Startwert ist ein vollständiges `PaperMetricsResponse` inkl. Pflichtfelder von `GatewayReadEnvelope` (`status`, `message`, `empty_state`, …). `account_ledger_recent` bleibt optional und wird in der UI weiter mit `?? []` behandelt — konsistent mit dem API-Vertrag.

## Checks (lokal)

- `pnpm check-types`
- `pnpm --dir apps/dashboard run check-types`
- `pnpm --dir apps/dashboard test -- paper-metrics-defaults health-service-reachability` (optional, gezielt)

## Offene Punkte

- Keine weiteren `tsc`-Fehler im Workspace-Scope (`@bitget-btc-ai/dashboard`, `@bitget-btc-ai/shared-ts`) nach diesen Fixes.
