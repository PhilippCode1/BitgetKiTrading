# 06 - Customer Webapp Foundation (Prompt 06)

Ziel: ein **lieferbares Endkunden-Portal-Fundament** mit klarer Trennung zur Operator-Konsole, serverseitiger BFF-Aggregation und expliziten `not_configured`/`backend_unavailable`-Zustaenden statt fiktiver Produktions-OK-Signale.

## Vorhandene Customer-Routen (App Router)

- `/portal` - Account-Overview + BFF-Statuspanel.
- `/portal/trial` - Trial-/Lifecycle-Status (wenn BFF/Gateway Daten liefern).
- `/portal/risk` - Risikoaufklaerung (statisch, produktrechtliche Hinweise).
- `/portal/exchange` - Read-only Verbindungsstatus (ohne Key-Material).
- `/portal/account/billing` - Vertrag-/Billing-Skelett.
- `/portal/trading` - Read-only Trading-Stub mit explizitem `not_configured`.
- `/portal/help` - Hilfe/Support-Einstieg.

Diese Routes leben unter `apps/dashboard/src/app/(customer)` und sind von `apps/dashboard/src/app/(operator)/console` getrennt.

## BFF- und Sicherheitsgrenzen

Server-only:

- `apps/dashboard/src/lib/customer-portal-summary.ts` aggregiert Daten nur serverseitig.
- `apps/dashboard/src/app/api/dashboard/customer/portal-summary/route.ts` exponiert redigierte JSON-Sicht.
- Gateway-Zugriff nur mit serverseitigem `DASHBOARD_GATEWAY_AUTHORIZATION`.
- Secret-Felder (`secret`, `token`, `api_key`, `password` usw.) werden aus Integrationsdaten gefiltert.

Public/browser:

- Nur redigierte Darstellungen in Customer-Seiten.
- Kein `NEXT_PUBLIC_*` fuer Exchange-/Provider-Secrets erforderlich.
- Portal bietet keine Live-Strategiemutation und keine Orderausloesung.

## Welche Daten sind echt vs. Stub

Echt (wenn Backend konfiguriert):

- `GET /v1/commerce/customer/me`
- `GET /v1/commerce/customer/lifecycle/me`
- `GET /v1/commerce/customer/integrations`

Explizite Stub-/Lueckenmarkierung:

- Trading/Signal-Zusammenfassung fuer Endkunden aktuell `not_configured` mit Code `NO_BFF_SIGNAL_SUMMARY_ENDPOINT`.
- Billing-Historie/Provider-Checkout ist noch kein integrierter Endkundenflow.

## Tests / lokale Evidence

- Jest-Test fuer Redaction/Sicherheitsgrenzen:  
  `apps/dashboard/src/lib/__tests__/customer-portal-summary.test.ts`
- Bestehender E2E-Customer-Journey-Smoketest:  
  `e2e/tests/customer-journey.spec.ts`

## Was fuer kommerzielles 10/10 noch fehlt

1. Vertrags-Lifecycle inkl. auditiertem Risk-Acknowledgement als echter Endkundenflow.
2. Read-only Signal-/Execution-Summary als produktiver BFF-Endpunkt (ohne Operator-Leaks).
3. Echte Billing-/Invoice-/Checkout-Integration mit Compliance-/Steuerprozess.
4. Externe Evidence fuer Domain/TLS/Consent/On-Call-/Support-SLA.
5. Abnahmebericht mit SHA + Umgebung + Product/Legal Signoff (L4/L5).
