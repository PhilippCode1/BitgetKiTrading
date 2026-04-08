# Dashboard: App-Router `page.tsx` (Stand Code-Scan)

Quelle: Glob `apps/dashboard/src/app/**/page.tsx` (Audit 2026-04-08).

## Öffentlich / Onboarding

- `/` — `(public)/page.tsx`
- `/welcome` — `welcome/page.tsx`
- `/onboarding` — `onboarding/page.tsx`

## Operator-Konsole (`/console/...`)

- `/console` — `console/page.tsx`
- `/console/ops`, `/terminal`, `/approvals`, `/health`, `/diagnostics`, `/self-healing`
- `/console/market-universe`, `/console/capabilities`, `/console/signals`, `/console/signals/[id]`, `/console/no-trade`
- `/console/live-broker`, `/console/live-broker/forensic/[id]`, `/console/shadow-live`, `/console/paper`
- `/console/learning`, `/console/strategies`, `/console/strategies/[id]`
- `/console/news`, `/console/news/[id]`, `/console/usage`, `/console/integrations`, `/console/help`
- `/console/admin` + Unterseiten (`rules`, `customers`, `billing`, `ai-governance`, …)
- `/console/account` + Unterseiten (`profile`, `broker`, `balance`, `language`, …)

**Hinweis:** Kein automatischer Beweis, dass jede Route unter realer Auth + Gateway „sinnvoll befüllt“ ist — siehe `INCOMPLETE_PAGES.md` und E2E `release-gate.spec.ts`.
