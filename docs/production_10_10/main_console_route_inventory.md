# Main Console Route Inventory

Stand: automatisierte Inventur fuer `apps/dashboard/src/app` mit
`python tools/check_main_console_routes.py --json`.

## Zusammenfassung

- UI-Routen: `62`
- API-/BFF-Routen: `45`
- Legacy-/Out-of-scope-Treffer (billing/customer/payment/...): `25`
- Ergebnis: Die Operator-Konsole ist stark, aber parallel bestehen Legacy-Portal-,
  Billing- und Customer/Commerce-Pfade.

## Route-Klassen

### A) Main-Console-Kern (relevant)

Diese Routen bilden den produktiven Kern fuer die private Main Console:

- ` /console`
- ` /console/ops`
- ` /console/terminal`
- ` /console/approvals`
- ` /console/health`
- ` /console/diagnostics`
- ` /console/self-healing`
- ` /console/market-universe`
- ` /console/signals`
- ` /console/signals/[id]`
- ` /console/no-trade`
- ` /console/live-broker`
- ` /console/live-broker/forensic/[id]`
- ` /console/shadow-live`
- ` /console/paper`
- ` /console/strategies`
- ` /console/strategies/[id]`
- ` /console/learning`
- ` /console/news`
- ` /console/news/[id]`
- ` /console/integrations`
- ` /console/help`
- ` /console/capabilities`
- ` /console/usage`
- ` /console/account`
- ` /console/account/language`
- ` /console/admin` (Owner/Admin intern)

Hinweis: Unter ` /console/account/*` und ` /console/admin/*` gibt es teils
Legacy-Seiten (siehe Klasse C), die nicht Main-Console-Zielstruktur sind.

### B) Zugangs-/Flow-Routen (relevant, aber nicht Main-Console-Bereich)

- ` /`
- ` /welcome`
- ` /onboarding`

Beobachtung:
- `middleware.ts` erzwingt Locale-Gate (`/welcome`) und Onboarding-Guard fuer
  Konsole mit `returnTo`.
- Diese Flows sind weiter notwendig, muessen aber inhaltlich auf private
  Main-Console-Nutzung reduziert bleiben.

### C) Legacy-/Out-of-scope-UI-Routen (deprecate/konsolidieren)

- Customer-Portal:
  - ` /portal`
  - ` /portal/account/billing`
  - ` /portal/billing`
  - ` /portal/contract`
  - ` /portal/exchange`
  - ` /portal/help`
  - ` /portal/performance`
  - ` /portal/performance/[id]`
  - ` /portal/risk`
  - ` /portal/trading`
  - ` /portal/trial`
- Billing/Payments/Customer im Console-Baum:
  - ` /console/account/billing`
  - ` /console/account/payments`
  - ` /console/admin/billing`
  - ` /console/admin/commerce-payments`
  - ` /console/admin/customers`
  - ` /console/admin/customers/[tenantId]`

Diese Seiten werden nicht blind entfernt; sie sind als Legacy markiert und
werden in spaeteren Prompts schrittweise konsolidiert.

## API-/BFF-Routen-Inventar

### Relevante Main-Console/Betriebs-APIs

- ` /api/health`
- ` /api/ready`
- ` /api/locale`
- ` /api/onboarding/status`
- ` /api/dashboard/edge-status`
- ` /api/dashboard/gateway/[...segments]`
- ` /api/dashboard/health/operator-report`
- ` /api/dashboard/live/stream`
- ` /api/dashboard/live-broker/executions/[id]/ops-risk-assist-context`
- ` /api/dashboard/self-healing/snapshot`
- ` /api/dashboard/self-healing/action`
- ` /api/dashboard/operator/ai-strategy-proposal-drafts`
- ` /api/dashboard/operator/ai-strategy-proposal-drafts/[draftId]`
- ` /api/dashboard/operator/ai-strategy-proposal-drafts/[draftId]/request-promotion`
- ` /api/dashboard/operator/ai-strategy-proposal-drafts/[draftId]/validate-deterministic`
- ` /api/dashboard/llm/operator-explain`
- ` /api/dashboard/llm/safety-incident-diagnose`
- ` /api/dashboard/llm/strategy-signal-explain`
- ` /api/dashboard/llm/assist/[segment]`
- ` /api/dashboard/chart-prefs`
- ` /api/dashboard/preferences/locale`
- ` /api/dashboard/preferences/ui-mode`
- ` /api/dashboard/admin/rules`
- ` /api/dashboard/admin/strategy-status`
- ` /api/dashboard/admin/llm-governance`

### Legacy-/Out-of-scope-Customer/Commerce-APIs

- ` /api/dashboard/customer/portal-summary`
- ` /api/dashboard/commerce/usage-ledger`
- ` /api/dashboard/commerce/usage-summary`
- ` /api/dashboard/commerce/customer/me`
- ` /api/dashboard/commerce/customer/history`
- ` /api/dashboard/commerce/customer/balance`
- ` /api/dashboard/commerce/customer/performance`
- ` /api/dashboard/commerce/customer/performance/export`
- ` /api/dashboard/commerce/customer/performance/report-pdf`
- ` /api/dashboard/commerce/customer/integrations`
- ` /api/dashboard/commerce/customer/integrations/telegram/start-link`
- ` /api/dashboard/commerce/customer/integrations/telegram/notify-prefs`
- ` /api/dashboard/commerce/customer/integrations/telegram/test`
- ` /api/dashboard/commerce/customer/payments`
- ` /api/dashboard/commerce/customer/payments/capabilities`
- ` /api/dashboard/commerce/customer/payments/deposit/checkout`
- ` /api/dashboard/commerce/customer/payments/deposit/intent/[intentId]`
- ` /api/dashboard/commerce/customer/payments/deposit/mock-complete`
- ` /api/dashboard/commerce/customer/payments/deposit/resume`
- ` /api/dashboard/admin/commerce-mutation`

## Doppelte/unklare Strukturstellen

- Konto/Abrechnung doppelt: ` /console/account/billing` und
  ` /console/admin/billing` plus Portal-Billing.
- Zahlungsbezug doppelt: ` /console/account/payments`,
  ` /console/admin/commerce-payments` und Customer-Payment-APIs.
- Customer-Verwaltung im Admin-Baum widerspricht Private-Owner-Ziel.
- `FlowNavBar` enthaelt weiter Marketing-/Kosten-Navigation, obwohl Produktziel
  private Main Console ist.

## Konsolidierungsprioritaet (ohne Blind-Loeschung)

1. Main-Console-Navigation auf private Kernbereiche reduzieren.
2. Legacy-Portal-/Billing-/Customer-Routen als `deprecated` markieren und aus
   primaerer Navigation entfernen.
3. API-Grenzen dokumentieren: operatorisch relevant vs. legacy-commerce.
4. Deutsche Empty-/Error-States fuer alle verbleibenden Main-Console-Seiten
   vereinheitlichen.

## Aktueller Navigationsstand im Code

- Primaere Main-Console-Navigation ist zentral hinterlegt in
  `apps/dashboard/src/lib/main-console/navigation.ts`.
- `SidebarNav` rendert diese Kernnavigation und blendet Admin/Owner fuer
  Nicht-Admin aus.
- `FlowNavBar` (Welcome/Onboarding) wurde auf private Main-Console-Einstiege
  reduziert; Marketing-/Kostenanker sind nicht mehr Teil dieses Flows.
