# bitget-btc-ai — API- und BFF-Endpunkt-Dossier (ChatGPT-Übergabe)

**Dokumenttyp:** Architektur der HTTP-Schichten (Browser → Next.js BFF → API-Gateway → Daten/Upstream).  
**Stand:** 2026-04-04.  
**Evidenz:** **verifiziert** = aus genannten Repo-Dateien; **dokumentiert** = nur Doku/Schlussfolgerung ohne Codezeile in diesem Schritt; **nicht verifiziert (Laufzeit)** = kein HTTP-Test in dieser Erstellungssession.

---

## 1. Überblick über die API-Architektur

| Schicht              | Rolle                                                                                    | Typische Pfade                                  | Auth                                                                                                                                                                        |
| -------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Browser**          | UI; ruft Dashboard-Host und ggf. `NEXT_PUBLIC_*`-URLs auf                                | `/console/*`, `/api/dashboard/*`, `/api/health` | Kein Gateway-JWT im Bundle bei Standard-BFF (siehe `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY`). **verifiziert:** `docs/api_gateway_security.md`, `apps/dashboard/src/lib/env.ts`. |
| **Next.js BFF**      | Server Route Handlers; trägt `DASHBOARD_GATEWAY_AUTHORIZATION`                           | `/api/dashboard/...`                            | Server-ENV nur. **verifiziert:** `apps/dashboard/src/lib/gateway-bff.ts`, `server-env.ts`.                                                                                  |
| **API-Gateway**      | FastAPI; CORS, Rate-Limits, Aggregation                                                  | `/health`, `/ready`, `/v1/*`                    | Öffentlich vs. JWT vs. interner Key je Route. **verifiziert:** `services/api-gateway/src/api_gateway/app.py`.                                                               |
| **Lesende „Proxys“** | Viele `routes_*_proxy.py` lesen **PostgreSQL direkt** im Gateway (kein HTTP zum Worker). | `/v1/signals/*`, `/v1/paper/*`, `/v1/news/*`, … | `require_sensitive_auth` auf Router-Ebene. **verifiziert:** `routes_signals_proxy.py`, `app.py` `include_router`.                                                           |
| **HTTP-Upstream**    | Ausgewählte Forwards (LLM, Live-Broker-Mutationen, …)                                    | z. B. `post_llm_orchestrator_json`              | `X-Internal-Service-Key` (`INTERNAL_API_KEY`). **verifiziert:** `llm_orchestrator_forward.py`, `docs/INTERNAL_SERVICE_ROUTES.md`.                                           |

**Request-Kette (Standard Operator-JSON):**  
Browser → `GET/POST https://<dashboard>/api/dashboard/gateway/v1/...` **oder** dedizierte BFF-Route → Next fügt `Authorization: <DASHBOARD_GATEWAY_AUTHORIZATION>` hinzu → `https://<gateway>/v1/...` → Gateway prüft JWT / Rollen → DB-Query oder HTTP-Forward.

**OpenAPI:** `shared/contracts/openapi/api-gateway.openapi.json` (Referenz; **nicht verifiziert:** vollständige Parität zum laufenden Code in diesem Schritt).

---

## 2. Tabelle der wichtigsten Frontend-BFF-Routen

Basis-Pfad: **`/api/dashboard/`** unter `apps/dashboard/src/app/api/dashboard/`. **verifiziert:** Dateibaum.

| BFF-Pfad (Muster)                                                                      | Methode | Zweck                                                                                                                                                                                                                                                             |
| -------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/dashboard/gateway/[...segments]`                                                 | GET     | Generischer Proxy: nur **`/v1/*`**; Timeout **60 s**; PDF/Octet-Stream durchgereicht. **verifiziert:** `gateway/[...segments]/route.ts`.                                                                                                                          |
| `/api/dashboard/gateway/[...segments]`                                                 | POST    | **Nur** `POST /v1/commerce/customer/contracts/*`; sonst **403**. **verifiziert:** dieselbe Datei.                                                                                                                                                                 |
| `/api/dashboard/llm/operator-explain`                                                  | POST    | Body-Validierung; Forward `POST /v1/llm/operator/explain`; Timeout **125 s**. **verifiziert:** `llm/operator-explain/route.ts`.                                                                                                                                   |
| `/api/dashboard/llm/strategy-signal-explain`                                           | POST    | Forward `POST /v1/llm/operator/strategy-signal-explain`; Timeout **125 s**; max. Signal-JSON **96k** Zeichen. **verifiziert:** `llm/strategy-signal-explain/route.ts`.                                                                                            |
| `/api/dashboard/llm/assist/[segment]`                                                  | \*      | Assistenz-Segment(e) zum Gateway (**verifiziert:** Route vorhanden).                                                                                                                                                                                              |
| `/api/dashboard/live/stream`                                                           | GET     | SSE/Long-Poll; Timeout **`null`** möglich. **verifiziert:** `gateway-upstream-fetch.ts` Kommentar zu SSE.                                                                                                                                                         |
| `/api/dashboard/edge-status`                                                           | GET     | Diagnose: Gateway `/health`, Operator-JWT-Probe `/v1/system/health`, Hinweise. **verifiziert:** `edge-status/route.ts`.                                                                                                                                           |
| `/api/dashboard/health/operator-report`                                                | GET     | PDF-Proxy zum Gateway. **verifiziert:** Route vorhanden.                                                                                                                                                                                                          |
| `/api/dashboard/system/...`                                                            | —       | **Hinweis:** zentrale System-Health kommt typisch über **Gateway-Proxy** `/api/dashboard/gateway/v1/system/health` aus `lib/api.ts`; kein separater `system`-Ordner unter BFF. **verifiziert:** `apps/dashboard/src/lib/api.ts` (Zeilen mit `/v1/system/health`). |
| `/api/dashboard/commerce/customer/*`                                                   | divers  | Kundenportal (Balance, Me, Payments, Telegram, …). **verifiziert:** Routen unter `commerce/customer/`.                                                                                                                                                            |
| `/api/dashboard/commerce/usage-summary`, `usage-ledger`                                | GET     | Usage-Ansichten. **verifiziert:** Routen vorhanden.                                                                                                                                                                                                               |
| `/api/dashboard/admin/rules`, `strategy-status`, `commerce-mutation`, `llm-governance` | divers  | Admin/Operator über BFF. **verifiziert:** Routen vorhanden.                                                                                                                                                                                                       |
| `/api/dashboard/preferences/*`, `chart-prefs`                                          | divers  | UI-Präferenzen. **verifiziert:** Routen vorhanden.                                                                                                                                                                                                                |

**Außerhalb `/api/dashboard/`:**

| Pfad          | Methode | Zweck                                                                                                                                               |
| ------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/health` | GET     | Liveness ohne Netzwerk; `status: ok` + Flags ob `API_GATEWAY_URL` / JWT-ENV gesetzt. **verifiziert:** `apps/dashboard/src/app/api/health/route.ts`. |
| `/api/ready`  | GET     | Readiness: `runGatewayBootstrapProbe()`; **503** wenn nicht betriebsbereit. **verifiziert:** `apps/dashboard/src/app/api/ready/route.ts`.           |

---

## 3. Tabelle der wichtigsten Gateway-Endpunkte

Präfixe aus `services/api-gateway/src/api_gateway/routes_*.py` und `app.py`. **verifiziert:** grep `APIRouter(prefix=`.

| Präfix / Pfad                                                | Router-Modul                              | Globale Auth am Router (`app.py`)                                                            |
| ------------------------------------------------------------ | ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| `GET /health`, `GET /ready`, `GET /`                         | `app.py`                                  | Keine                                                                                        |
| `/v1/deploy/*`                                               | `routes_deploy_readiness.py`              | Keine (eingebunden vor sensiblen Routern)                                                    |
| `/v1/meta/*`                                                 | `routes_public_meta.py`                   | Keine                                                                                        |
| `/v1/auth/*`                                                 | `routes_auth.py`                          | Pro-Route                                                                                    |
| `/v1/commerce/*` (intern/Metering)                           | `routes_commerce.py`                      | Pro-Route                                                                                    |
| `/v1/commerce/customer/*`                                    | `routes_commerce_customer.py`             | Pro-Route                                                                                    |
| `/v1/commerce/admin/customer/*`                              | `routes_commerce_customer.py`             | Pro-Route                                                                                    |
| `/v1/commerce/payments/*`, `/v1/commerce/admin/payments/*`   | `routes_commerce_payments.py`             | Pro-Route                                                                                    |
| `/v1/commerce/customer/contracts/*`, Webhooks                | `routes_commercial_contracts.py`          | Pro-Route                                                                                    |
| `/v1/commerce/customer/billing/*`, admin billing             | `routes_commerce_subscription_billing.py` | Pro-Route                                                                                    |
| `/v1/commerce/customer/profit-fee/*`, admin                  | `routes_commerce_profit_fee.py`           | Pro-Route                                                                                    |
| `/v1/commerce/admin/treasury/*`, `settlements/*`             | `routes_commerce_settlement.py`           | Pro-Route                                                                                    |
| `/db/health`                                                 | `routes_db.py`                            | **verifiziert:** Pfad ohne `/v1`-Präfix in Router-Definition                                 |
| `/events/*`                                                  | `routes_events.py`                        | `Depends` in Modul (**verifiziert:** Import in `app.py`)                                     |
| `/v1/live/*`                                                 | `routes_live.py`                          | Pro-Route (SSE/Cookie)                                                                       |
| `/v1/live-broker/*` (Lesend)                                 | `routes_live_broker_proxy.py`             | `audited_sensitive` pro Handler                                                              |
| `/v1/live-broker/*` (Operator)                               | `routes_live_broker_operator.py`          | Mutationsrollen                                                                              |
| `/v1/live-broker/safety/*`                                   | `routes_live_broker_safety.py`            | Safety-Mutationen                                                                            |
| `/v1/signals/*`                                              | `routes_signals_proxy.py`                 | **`Depends(require_sensitive_auth)`** am Router                                              |
| `/v1/paper/*`                                                | `routes_paper_proxy.py`                   | idem                                                                                         |
| `/v1/news/*`                                                 | `routes_news_proxy.py`                    | idem                                                                                         |
| `/v1/alerts/*`                                               | `routes_alerts_proxy.py`                  | idem                                                                                         |
| `/v1/monitor/*`                                              | `routes_monitor_proxy.py`                 | idem                                                                                         |
| `/v1/registry/*`                                             | `routes_registry_proxy.py`                | idem                                                                                         |
| `/v1/market-universe/*`                                      | `routes_market_universe.py`               | idem                                                                                         |
| `/v1/learning/*`, `/v1/backtests/*`                          | `routes_learning_proxy.py`                | idem                                                                                         |
| `/v1/admin/*`                                                | `routes_admin.py`                         | idem                                                                                         |
| `/v1/admin/paper/*`                                          | `routes_admin_paper.py`                   | idem                                                                                         |
| `/v1/llm/operator/*`                                         | `routes_llm_operator.py`                  | `require_sensitive_auth` pro **POST**                                                        |
| `/v1/llm/assist/*`                                           | `routes_llm_assist.py`                    | Rollen-spezifisch (`require_admin_read` / `require_billing_read` / `require_sensitive_auth`) |
| `/v1/system/health`, `/v1/system/health/operator-report.pdf` | `routes_system_health.py`                 | **`require_operator_aggregate_auth`**                                                        |

**Priorisiert für Produktbetrieb (Auswahl):** `/ready`, `/v1/system/health`, `/v1/signals/recent`, `/v1/signals/facets`, `/v1/paper/*`, `/v1/live-broker/*`, `/v1/monitor/alerts/open`, `/v1/alerts/outbox/recent`, `/v1/meta/surface`.

---

## 4. Wichtige Downstream-Weiterleitungen

| Gateway-Bereich                                                                                                                                                                                         | Downstream-Realität                                                                     | Beleg                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `/v1/signals/*`, `/v1/paper/*`, `/v1/news/*`, `/v1/alerts/*`, `/v1/monitor/*`, `/v1/learning/*`, `/v1/backtests/*`, `/v1/registry/*`, `/v1/market-universe/*`, große Teile `/v1/live-broker/*` (Lesend) | **PostgreSQL** im Gateway-Prozess (`psycopg`, `get_database_url`)                       | **verifiziert:** jeweilige `routes_*_proxy.py` / `routes_learning_proxy.py` / `routes_live_broker_proxy.py`                            |
| `/v1/llm/operator/*` (POST)                                                                                                                                                                             | **HTTP** → `llm-orchestrator` (`post_llm_orchestrator_json`, Timeout Gateway **120 s**) | **verifiziert:** `routes_llm_operator.py`, `llm_orchestrator_forward.py`                                                               |
| `/v1/llm/assist/*`                                                                                                                                                                                      | **HTTP** → Orchestrator (gleiche Forward-Hilfe)                                         | **verifiziert:** `routes_llm_assist.py` Import                                                                                         |
| Live-Broker **Mutationen** / Forward-Pfade                                                                                                                                                              | **HTTP** zu live-broker mit `INTERNAL_API_KEY` (siehe Live-Forward-Module)              | **verifiziert:** `docs/api_gateway_security.md`; **dokumentiert:** Einzelpfadliste ohne erneutes Durchscannen aller `live_broker_*.py` |

**Worker-Dienste** (market-stream, signal-engine, …) speisen **Redis/DB**; das Gateway liest für die meisten Dashboard-JSONs **nicht** deren HTTP-Ports aus. **verifiziert:** Architektur der genannten Proxy-Router.

---

## 5. Fehlerformat und Fehler-Mapping

### 5.1 API-Gateway (FastAPI)

| Situation                                  | JSON-Form                                                                                                                    | **verifiziert**                                |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `HTTPException`, **nicht** `PRODUCTION`    | `{ "detail": … }` — `detail` string oder Objekt (z. B. `code`, `message`)                                                    | `api_gateway/errors.py` `shape_http_exception` |
| `HTTPException`, **`PRODUCTION=true`**     | `{ "error": { "code", "message", "status" } }` — generische Texte, sofern nicht strukturiertes `detail` mit `code`/`message` | dieselbe Datei                                 |
| `RequestValidationError`, **Production**   | `{ "error": { "code": "VALIDATION_ERROR", "message": "Invalid request body.", "status": 422 } }`                             | `app.py` `_gateway_validation_handler`         |
| `RequestValidationError`, **non-Prod**     | `{ "detail": exc.errors() }`                                                                                                 | `app.py`                                       |
| Unbehandelte **Exception** bei `GET /v1/*` | **HTTP 200** mit **Degrade-Envelope** (`merge_read_envelope`, `status: degraded`, …) — kein roher 500 fürs Dashboard         | `app.py` `_gateway_unhandled_read_degrade`     |

**BFF-Hinweis:** Gateway-Antworten werden vom BFF oft **transparent** durchgereicht (Text + Status), siehe `gateway/[...segments]/route.ts`.

### 5.2 Dashboard BFF (Next.js)

| Code    | Bedeutung                                        | JSON-Beispiel (sinngemäß)                                                                                                            | **verifiziert**                               |
| ------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| **503** | JWT-ENV fehlt                                    | `detail`: „DASHBOARD_GATEWAY_AUTHORIZATION fehlt — Bearer-JWT …“, `code`: `DASHBOARD_GATEWAY_AUTH_MISSING`, `layer`: `dashboard-bff` | `gateway-bff.ts` `requireOperatorGatewayAuth` |
| **503** | `API_GATEWAY_URL` fehlt (Production)             | `code`: `API_GATEWAY_URL_MISSING`                                                                                                    | `gateway-upstream.ts`                         |
| **502** | Transport zum Gateway (ECONNREFUSED, Timeout, …) | `code`: `GATEWAY_TRANSPORT_FAILED`, Text mit `API-Gateway nicht erreichbar`                                                          | `gateway-upstream.ts`                         |
| **400** | BFF-Validierung (z. B. LLM-Body)                 | `detail` wie „question_de must be …“                                                                                                 | `llm/operator-explain/route.ts`               |

**Stabile BFF-Codes:** `DashboardBffErrorCode` in `apps/dashboard/src/lib/gateway-bff-errors.ts`.

### 5.3 Timeouts (BFF → Gateway)

| Kontext                                   | Timeout                                           | **verifiziert**                              |
| ----------------------------------------- | ------------------------------------------------- | -------------------------------------------- |
| Standard `fetchGatewayUpstream`           | **60 s** (`GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS`)  | `gateway-upstream-fetch.ts`                  |
| Commerce-Kurzpfade                        | **12 s** (`GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS`) | dieselbe Datei                               |
| Generischer GET-Proxy `[...segments]`     | **60 s**                                          | `gateway/[...segments]/route.ts`             |
| `operator-explain` BFF                    | **125 s**                                         | `llm/operator-explain/route.ts`              |
| Gateway → Orchestrator (Operator-Explain) | **120 s**                                         | `routes_llm_operator.py` `timeout_sec=120.0` |
| SSE                                       | kein Abort (`timeoutMs: null` möglich)            | `gateway-upstream-fetch.ts` Kommentar        |

---

## 6. Auth pro Endpunktklasse

| Klasse                                           | Anforderung                                                                                                                                                                                                                 | **verifiziert**                                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Gateway Liveness                                 | Keine                                                                                                                                                                                                                       | `GET /health`                                                                                |
| Gateway Readiness                                | Keine                                                                                                                                                                                                                       | `GET /ready`                                                                                 |
| Öffentliche Meta / Deploy-Readiness              | Keine Secrets                                                                                                                                                                                                               | `routes_public_meta.py`, `routes_deploy_readiness.py`                                        |
| Sensible Lesepfade `/v1/signals`, `/v1/paper`, … | JWT `gateway:read` **oder** `X-Gateway-Internal-Key` / Legacy (wenn erlaubt)                                                                                                                                                | `app.py` `Depends(require_sensitive_auth)` auf Proxy-Routern; `docs/api_gateway_security.md` |
| `GET /v1/system/health`                          | **`require_operator_aggregate_auth`** (anders als einfaches `gateway:read`)                                                                                                                                                 | `routes_system_health.py`                                                                    |
| `POST /v1/llm/operator/*`                        | `require_sensitive_auth` + Audit                                                                                                                                                                                            | `routes_llm_operator.py`                                                                     |
| `POST /v1/llm/assist/*`                          | je Route `require_admin_read` / `require_billing_read` / `require_sensitive_auth`                                                                                                                                           | `routes_llm_assist.py`                                                                       |
| BFF                                              | Viele geschützte Routen: `requireOperatorGatewayAuth()` (`gateway-bff.ts`); **Ausnahme** z. B. `GET /api/dashboard/edge-status` — eigene Bootstrap-Probe ohne vorherigen Hard-Fail. **verifiziert:** `edge-status/route.ts` |

---

## 7. Kritische Endpunkte für Produktbetrieb

| Endpunkt                                       | Grund                                              |
| ---------------------------------------------- | -------------------------------------------------- |
| `GET /ready` (Gateway)                         | Orchestrierung Compose / Monitoring                |
| `GET /api/ready` (Dashboard)                   | Container-Healthcheck laut `docker-compose.yml`    |
| `GET /v1/system/health`                        | Operator-Aggregat (DB, Redis, Services, Warnungen) |
| `GET /v1/signals/recent`, `/v1/signals/facets` | Signal-Center                                      |
| `GET /v1/live-broker/runtime`, Orders, Fills   | Live-Broker-Sicht                                  |
| `GET /v1/monitor/alerts/open`                  | Incident-Sicht                                     |
| `GET /v1/meta/surface`                         | Evidenz ohne Auth                                  |

---

## 8. Kritische Endpunkte für KI-Funktionen

| Pfad                                              | Schicht | Bemerkung                                                                                                    |
| ------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ |
| `POST /api/dashboard/llm/operator-explain`        | BFF     | Validiert Eingabe, dann Gateway                                                                              |
| `POST /v1/llm/operator/explain`                   | Gateway | Forward Orchestrator `/llm/analyst/operator_explain`, Timeout 120 s                                          |
| `POST /api/dashboard/llm/strategy-signal-explain` | BFF     | Zweite KI-Strecke (Produktbeschreibung `PRODUCT_STATUS.md`)                                                  |
| `POST /v1/llm/operator/strategy-signal-explain`   | Gateway | Forward                                                                                                      |
| `POST /v1/llm/assist/*`                           | Gateway | Zusätzliche Assist-Rollen; nicht alle im Dashboard als BFF exponiert (**dokumentiert:** `PRODUCT_STATUS.md`) |

**Orchestrator** (intern, nicht vom Browser): `POST /llm/analyst/*` mit `X-Internal-Service-Key`. **verifiziert:** `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`.

---

## 9. Verifizierte Testläufe oder begründete Nicht-Verifizierbarkeit

| Aktivität                                                        | Ergebnis                                                                                                                                 |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| HTTP-Aufrufe gegen laufenden Gateway/Dashboard in dieser Session | **nicht verifiziert (Laufzeit)** — kein gestarteter Stack hier.                                                                          |
| Code-/Pfad-Audit BFF + Gateway                                   | **verifiziert** — Dateien wie oben referenziert.                                                                                         |
| Empfohlene Smoke-Kommandos (Repo)                                | `pnpm api:integration-smoke`, `pnpm smoke`, `pnpm e2e`, `pnpm release:gate` — **dokumentiert:** `API_INTEGRATION_STATUS.md` Abschnitt 9. |

---

## 10. Schwachstellen und offene Lücken

| Thema                              | Risiko / Lücke                                                                                                                                                  |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GET /v1/\* unhandled Exception** | Absichtlich **HTTP 200 + degraded** — Clients müssen `status` im Envelope prüfen, nicht nur HTTP-Code. **verifiziert:** `app.py`.                               |
| **Generischer BFF POST**           | Nur Contracts-POST erlaubt — verhindert breiten Mutation-Proxy, erfordert neue BFF-Routen für weitere POSTs. **verifiziert:** `gateway/[...segments]/route.ts`. |
| **OpenAPI vs. Code**               | Kann hinterherhinken; keine vollständige Diff-Prüfung in diesem Dokument. **nicht verifiziert.**                                                                |

---

## 11. Übergabe an ChatGPT

1. Unterscheide **BFF-Pfad** (`/api/dashboard/...`) und **Gateway-Pfad** (`/v1/...`).
2. Standard-Dashboard-Daten: Gateway **liest Postgres**, nicht zwingend Worker-HTTP.
3. KI: Gateway forward zu **llm-orchestrator** mit **INTERNAL_API_KEY**; OpenAI-Key nur dort.
4. Fehler: **Production** verschärft Gateway-JSON (`error`-Envelope); BFF nutzt `detail` + `code` + `layer`.
5. Diagnose: **`GET /api/dashboard/edge-status`**.

---

## 12. Anhang mit Beispielen für Requests und Responses

### 12.1 Gateway Liveness (ohne Auth)

```http
GET /health HTTP/1.1
Host: 127.0.0.1:8000
```

**Antwort (verifiziert aus Code):** `{"status":"ok"}` — `app.py`.

### 12.2 System-Health (mit JWT)

```http
GET /v1/system/health HTTP/1.1
Host: 127.0.0.1:8000
Authorization: Bearer <jwt_mit_operator_aggregate_berechtigung>
```

**Antwort:** großes JSON mit `database`, `redis`, `services`, `warnings`, … — **verifiziert:** `routes_system_health.py` `compute_system_health_payload`.

### 12.3 BFF Operator-Explain

```http
POST /api/dashboard/llm/operator-explain HTTP/1.1
Host: 127.0.0.1:3000
Content-Type: application/json

{"question_de":"Was bedeutet Live-Gate?","readonly_context_json":{}}
```

**Fehlerbeispiel BFF (JWT fehlt):** HTTP **503**, Body mit `detail` sinngemäß: _„DASHBOARD_GATEWAY_AUTHORIZATION fehlt — Bearer-JWT (gateway:read) in der Dashboard-ENV …“_ — **verifiziert:** `gateway-bff.ts`.

### 12.4 Gateway LLM nicht konfiguriert

**Antwort sinngemäß:** HTTP **503**, `detail`: `code` **`LLM_ORCH_UNAVAILABLE`**, `message` mit Text aus `RuntimeError` (z. B. Basis-URL fehlt) — **verifiziert:** `routes_llm_operator.py`.

### 12.5 Production HTTPException-Envelope

**Antwort sinngemäß:**  
`{"error":{"code":"SERVICE_UNAVAILABLE","message":"Service temporarily unavailable.","status":503}}`  
(bzw. spezifischer `code`/`message` aus strukturiertem `detail`) — **verifiziert:** `errors.py`.

---

_Ende der Übergabedatei._
