# 29 — Commerce-, Account- und Admin-BFF (Rollen, Auth, Proxy)

**Stand:** 2026-04-05  
**Bezug:** `docs/chatgpt_handoff/03_ENV_SECRETS_AUTH_MATRIX.md` (Secrets, `DASHBOARD_GATEWAY_AUTHORIZATION`), `docs/chatgpt_handoff/04_API_BFF_ENDPOINT_DOSSIER.md` (Schichtenmodell Browser → BFF → Gateway).

---

## 1. Zielbild

| Rolle / Fläche                       | Bedeutung im Dashboard                                                                                         | BFF-Auth                                                   | Hinweis                                                                                                             |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Kundenbezogen**                    | Commerce-Kontext (`/v1/commerce/customer/*` über dedizierte Routen + Verträge über Gateway-POST)               | `requireOperatorGatewayAuth()` (serverseitiger BFF-Bearer) | Kein Gateway-JWT im Browser; Gateway entscheidet über Kundenkontext (Cookies/Token am Gateway, je Route).           |
| **Operator-Konsole**                 | Lesende und erklärende Tools (generischer `GET /api/dashboard/gateway/v1/*`, LLM-BFF, Live-Stream, Health/PDF) | Dito                                                       | Breiter **GET**-Proxy bewusst: ein Einstieg für `/v1`-JSON; Schutz = Deployment + Gateway-JWT-Scopes + Same-Origin. |
| **Admin / privilegierte Mutationen** | `/api/dashboard/admin/*`, strikte Commerce-Mutations-Allowlist                                                 | Dito + **Allowlists** für Schreibpfade                     | Kein generischer `POST` auf beliebiges `/v1` am Catch-All.                                                          |

**Middleware:** `apps/dashboard/src/middleware.ts` behandelt `/api/*` als Bypass (kein Locale-/Onboarding-Zwang). Jede BFF-Route muss ihre eigene Logik haben — für Gateway-Proxys ist das `requireOperatorGatewayAuth()`.

---

## 2. Zentrale Auth-Regel (alle Gateway-BFF-Pfade)

- **Quelle:** `apps/dashboard/src/lib/gateway-bff.ts` — `requireOperatorGatewayAuth()`.
- **ENV:** `DASHBOARD_GATEWAY_AUTHORIZATION` (vollständiger `Authorization`-Header-Wert), nur Next-Server.
- **Semantik:** Dienst-Credential für die BFF, **nicht** die Session eines einzelnen UI-Nutzers. Autorisierung pro Ressource erfolgt am **API-Gateway** (siehe 03/04).

Bei fehlendem Header: **503** mit `DASHBOARD_GATEWAY_AUTH_MISSING` (`jsonDashboardBffError`).

---

## 3. Route-Gruppen (final)

### 3.1 Generischer Gateway-Catch-All

| BFF-Pfad                               | Methoden               | Upstream / Verhalten                                                                                                                                                                                                           |
| -------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/api/dashboard/gateway/[...segments]` | **GET**                | Nur Segmente mit Prefix `v1` → `GET /v1/...` mit Retry; PDF/Octet-Stream durchgereicht.                                                                                                                                        |
| Dasselbe                               | **POST**               | Nur Pfade, die exakt `genericGatewayBffAllowsPostPath` erfüllen: `/v1/commerce/customer/contracts` und `/v1/commerce/customer/contracts/*` (Allowlist in `apps/dashboard/src/lib/dashboard-bff-allowlists.ts`). Sonst **403**. |
| Dasselbe                               | **PUT, PATCH, DELETE** | **405** mit `Allow: GET, POST` — keine versteckten generischen Mutationen.                                                                                                                                                     |

**Nachschärfung (Umsetzung 29):** Früher genügte `path.startsWith("/v1/commerce/customer/contracts")`, wodurch z. B. `/v1/commerce/customer/contractsX` fälschlich erlaubt war. Jetzt strikter Präfix über `genericGatewayBffAllowsPostPath`.

### 3.2 Dedizierte Commerce-BFF (Kundenportal)

Alle unter `apps/dashboard/src/app/api/dashboard/commerce/**/route.ts`: typisch `requireOperatorGatewayAuth` + `fetchGatewayUpstream` zu festen `/v1/commerce/...`-Pfaden (inkl. Zahlungen, Telegram, Performance, Usage).

**Sonderfall Mutation ohne Standard-Bearer:**  
`commerce/customer/payments/deposit/mock-complete` nutzt `fetchGatewayWithoutBearer` + `X-Payment-Mock-Secret` (`PAYMENT_MOCK_WEBHOOK_SECRET`) — nur für Mock/Test-Pfad am Gateway, weiterhin BFF-seitig abgeschottet.

### 3.3 Admin-BFF

| BFF-Pfad                                 | Zweck                                                                                                                                             |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/dashboard/admin/rules`             | GET/POST → Gateway `/v1/admin/rules`                                                                                                              |
| `/api/dashboard/admin/strategy-status`   | POST → `/v1/admin/strategy-status`                                                                                                                |
| `/api/dashboard/admin/llm-governance`    | GET → `/v1/admin/llm-governance`                                                                                                                  |
| `/api/dashboard/admin/commerce-mutation` | POST mit Body `{ method, path, payload }`; nur Pfade/Methoden aus `commerceAdminMutationAllowed()` (dieselbe Datei `dashboard-bff-allowlists.ts`) |

**Allowlist Commerce-Admin-Mutation (POST-Ziele):**

- `/v1/commerce/admin/customer/lifecycle/transition`
- `/v1/commerce/admin/customer/wallet/adjust`
- `/v1/commerce/admin/customer/lifecycle/set-email-verified`

**PATCH:** nur `^/v1/commerce/admin/billing/tenant/[^/]+/dunning$`.

### 3.4 Weitere operatorbezogene BFF (ohne `/admin`-Prefix)

- `llm/operator-explain`, `llm/strategy-signal-explain`, `llm/assist/[segment]` — Gateway-Forward mit Validierung.
- `live/stream`, `edge-status`, `health/operator-report` — jeweils `requireOperatorGatewayAuth` wo Gateway-Zugriff.

### 3.5 Präferenzen / UI (kein Gateway-JWT)

- `/api/dashboard/preferences/locale`, `preferences/ui-mode`, `chart-prefs` — Cookies, keine `DASHBOARD_GATEWAY_AUTHORIZATION`-Abhängigkeit für die reine UI-State-Speicherung.

---

## 4. Bewusste Architektur-Entscheidungen

1. **Breiter GET unter `/api/dashboard/gateway/v1/*`:** Ersetzt direkte Browser-Aufrufe zum Gateway für Lesen. Einschränkung auf Produkt-Ebene wäre eine große Allowlist-Pflege; stattdessen: Vertrauen in Gateway-RBAC, Secret-Handling (03) und Same-Origin.
2. **Kein generischer POST/PUT/PATCH/DELETE** am Catch-All: Nur Vertrags-POST wie oben; andere Schreibvorgänge über dedizierte BFF-Routen oder `admin/commerce-mutation`.
3. **„Kunde“ vs. „Operator“ in der BFF:** Die BFF trägt immer dasselbe Server-Credential; die **fachliche** Trennung Kunde/Admin entsteht durch **Gateway-Routen** und **welche BFF-Endpunkte** die UI überhaupt aufruft.

---

## 5. Nachweise

### 5.1 Automatisierte Tests

- `apps/dashboard/src/lib/__tests__/dashboard-bff-allowlists.test.ts` — Prüfung der POST-Vertrags-Allowlist (inkl. Ablehnung von `contractsX`) und der Commerce-Admin-Mutation-Allowlist.
- `apps/dashboard/src/lib/__tests__/gateway-bff-errors.test.ts` — JSON-Fehlerform der BFF.

**Befehl (Paket dashboard):** `pnpm test -- dashboard-bff-allowlists` sowie `pnpm test -- gateway-bff-errors` (im Verzeichnis `apps/dashboard`).

**Ergebnis (lokal, 2026-04-05):** jeweils Jest **PASS**, 5 bzw. 1 Test.

### 5.2 Typecheck (Monorepo)

**Befehl (Repo-Root):** `pnpm check-types`

**Ergebnis (lokal, 2026-04-05):** `pnpm check-types` — Turbo 2.8.20, beide Pakete `@bitget-btc-ai/shared-ts` und `@bitget-btc-ai/dashboard` erfolgreich (`tsc --noEmit`).

### 5.3 Manuelle API-Matrix (optional, Laufzeit)

Voraussetzung: laufendes Dashboard + gesetztes `DASHBOARD_GATEWAY_AUTHORIZATION`.

- `GET /api/dashboard/gateway/v1/system/health` — 200/401 je nach Gateway, nicht 503 `DASHBOARD_GATEWAY_AUTH_MISSING`, wenn BFF-ENV ok.
- `POST /api/dashboard/gateway/v1/commerce/customer/contractsX` — **403** (ungültiger Vertrags-Pfad).
- `PATCH /api/dashboard/gateway/v1/foo` — **405**.
- `POST /api/dashboard/admin/commerce-mutation` mit Body `{ "method": "POST", "path": "/v1/commerce/admin/customer/wallet/adjust", "payload": {} }` — nur sinnvoll mit gültigem Gateway; bei nicht erlaubtem Pfad **403** `path_not_allowed`.

---

## 6. Geänderte / neue Artefakte (Umsetzung)

| Datei                                                                   | Rolle                                              |
| ----------------------------------------------------------------------- | -------------------------------------------------- |
| `apps/dashboard/src/lib/dashboard-bff-allowlists.ts`                    | Zentrale Allowlists + Hilfsfunktionen              |
| `apps/dashboard/src/app/api/dashboard/gateway/[...segments]/route.ts`   | Nutzung Allowlist; PUT/PATCH/DELETE → 405          |
| `apps/dashboard/src/app/api/dashboard/admin/commerce-mutation/route.ts` | Import aus Allowlist-Modul                         |
| `apps/dashboard/src/lib/gateway-bff.ts`                                 | Klarstellung JSDoc: BFF-Bearer ≠ Endnutzer-Session |
| `apps/dashboard/src/lib/__tests__/dashboard-bff-allowlists.test.ts`     | Regressionstests                                   |
| `docs/cursor_execution/29_commerce_account_admin_bff.md`                | Nachweis Route-Gruppen + Auth                      |

---

## 7. Offene Punkte

- **[FUTURE]** Feinere GET-Allowlist am Gateway-Catch-All, falls das Produkt eine explizite Pfad-Policy verlangt (hoher Pflegeaufwand).
- **[RISK]** Wie bei jeder BFF mit einem Server-JWT: XSS auf derselben Origin könnte dieselben BFF-Endpunkte triggern wie die legitime UI — Mitigation: CSP, sichere UI-Patterns, Gateway-Rate-Limits.
