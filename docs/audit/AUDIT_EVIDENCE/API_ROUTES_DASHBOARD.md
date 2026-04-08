# Dashboard: Next.js API `route.ts` (BFF)

Quelle: Glob `apps/dashboard/src/app/api/**/route.ts` — **43** Dateien (Audit 2026-04-08).

## Kategorien (kurz)

- **Health / Ready:** `api/health`, `api/ready`, `api/dashboard/edge-status`, `api/dashboard/health/operator-report`
- **Gateway-Proxy:** `api/dashboard/gateway/[...segments]`
- **LLM / KI:** `api/dashboard/llm/operator-explain`, `strategy-signal-explain`, `safety-incident-diagnose`, `assist/[segment]`
- **Self-Healing:** `api/dashboard/self-healing/snapshot`, `action`
- **Live:** `api/dashboard/live/stream`
- **Operator / Admin:** diverse `operator/*`, `admin/*`
- **Commerce / Kunde:** `api/dashboard/commerce/customer/*`
- **Preferences:** `locale`, `ui-mode`, `chart-prefs`

**DoD für „kein toter Button“:** Jede UI-Aktion, die diese Routen triggert, muss in E2E oder Vertrags-Tests einen erwarteten HTTP-Status + Nutzerfeedback haben (kein leeres `catch` ohne UI).
