# 30 — Fehler-, Timeout- und Retry-Architektur (Gateway, BFF, UI)

**Stand:** 2026-04-05  
**Bezug:** `docs/chatgpt_handoff/04_API_BFF_ENDPOINT_DOSSIER.md` (Schichten), `docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md` (Ursachenmatrix).

---

## 1. Zielbild

| Schicht                         | Einheitliche Signale                                                                               | Operator-Hinweis                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| **API-Gateway (HTTP-Fehler)**   | Produktion: `{ "error": { "code", "message", "status", "layer": "api-gateway" } }`                 | Codes aus `map_status_to_code` / Handler; keine zufälligen Freitexte in Prod. |
| **API-Gateway (Lesen /v1)**     | `merge_read_envelope`: `status` ∈ `ok` \| `empty` \| `degraded` + `read_envelope_contract_version` | `message`, `next_step`, `degradation_reason` (maschinenlesbar).               |
| **Dashboard-BFF**               | `jsonDashboardBffError`: `code`, `layer: "dashboard-bff"`, `detail`                                | Transport/Config, nicht fachliche Degradierung.                               |
| **Dashboard-Client (`api.ts`)** | `ApiFetchError` mit `kind`, optional `code`/`layer` aus JSON                                       | `extractErrorDetailFromBody` versteht Gateway-`error`-Envelope.               |
| **UI**                          | `GatewayReadNotice` + sichtbarer Banner bei `degraded`                                             | `data-gateway-read-status`, Logs bei HTTP-200+degraded.                       |

**Wichtig:** HTTP **200** mit `status: "degraded"` ist **kein Erfolg** — UI muss Envelope-Felder auswerten; BFF setzt zusätzlich `X-Gateway-Read-Status` (und optional `X-Gateway-Degradation-Reason`) auf JSON-Proxys.

---

## 2. Finale Fehlerverträge (Beispiel-Payloads)

### 2.1 HTTP 400 (Produktion, generisch)

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "The request was invalid.",
    "status": 400,
    "layer": "api-gateway"
  }
}
```

### 2.2 HTTP 401

```json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Authentication required.",
    "status": 401,
    "layer": "api-gateway"
  }
}
```

### 2.3 HTTP 422 (Validierung, Produktion)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request body.",
    "status": 422,
    "layer": "api-gateway"
  }
}
```

_Nicht-Produktion:_ weiterhin `{"detail": [...]}` (FastAPI `RequestValidationError`).

### 2.4 HTTP 502 / 503

```json
{
  "error": {
    "code": "BAD_GATEWAY",
    "message": "Upstream service error.",
    "status": 502,
    "layer": "api-gateway"
  }
}
```

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Service temporarily unavailable.",
    "status": 503,
    "layer": "api-gateway"
  }
}
```

### 2.5 Leser-Envelope „degraded“ (HTTP 200)

Typisch aus `merge_read_envelope` oder globalem GET-`/v1/*`-Exception-Handler:

```json
{
  "items": [],
  "limit": 50,
  "status": "degraded",
  "message": "Daten konnten nicht geladen werden.",
  "empty_state": true,
  "degradation_reason": "database_error",
  "next_step": "Postgres pruefen, Migration-Job ausfuehren. In Docker: DATABASE_URL auf den Service `postgres` zeigen lassen (z. B. BITGET_USE_DOCKER_DATASTORE_DSN=true).",
  "read_envelope_contract_version": 1
}
```

### 2.6 HTTP 500 (nicht abgefangene Nicht-GET-Fehler)

```json
{
  "detail": "Internal Server Error",
  "code": "INTERNAL_SERVER_ERROR",
  "layer": "api-gateway"
}
```

### 2.7 Dashboard-BFF (503, fehlendes Gateway-JWT)

```json
{
  "detail": "DASHBOARD_GATEWAY_AUTHORIZATION fehlt — …",
  "code": "DASHBOARD_GATEWAY_AUTH_MISSING",
  "layer": "dashboard-bff"
}
```

---

## 3. Timeouts und Retry (Referenz)

| Stelle                                          | Wert                                          | Verhalten                                                                                       |
| ----------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `fetchGatewayUpstream` Default                  | 60 s (`GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS`)  | `AbortSignal.timeout`, `cache: "no-store"`.                                                     |
| Commerce-BFF / Vertrags-POST                    | 12 s (`GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS`) | Kürzer als Standard-GET.                                                                        |
| `fetchGatewayGetWithRetry`                      | bis 3 Versuche                                | Retry bei transientem Netzwerk **oder** HTTP 408, 429, 502, 503, 504; Backoffs 320 ms / 960 ms. |
| **Kein Retry** bei                              | 401, 403, 404, 422                            | Vermeidet Auth-/Validierungs-Loops.                                                             |
| Browser → BFF (`getJsonViaDashboardBffExecute`) | 22 s pro Versuch, bis 3 Versuche              | Gleiche retryable Status wie oben; Backoff 220 / 600 ms.                                        |
| SSR `getJsonServer`                             | 60 s                                          | `fetchGatewayGetWithRetry` mit 60 s.                                                            |
| BFF-Response-Cache (Browser)                    | fresh 5 s, stale 90 s                         | Nur erfolgreiche JSON-Antworten; `degraded` bleibt im Body sichtbar.                            |

**Hinweis:** HTTP **200** mit `status: "degraded"` wird **nicht** retried (korrekt: kein transienter Upstream-Fehler).

---

## 4. Caching

- Gateway-Upstream-Fetches: durchgängig `cache: "no-store"`.
- BFF Gateway-Route (`/api/dashboard/gateway/...`): JSON-Antworten mit `Cache-Control: no-store` + Leser-Status-Header.
- Browser-seitiger BFF-Map-Cache (`api.ts`): kurzes fresh window — bei schnellem Wechsel ok→degraded kann kurz alte Daten angezeigt werden; **[RISK]** gering, Ops-Hinweis in 08.

---

## 5. UI: Degradierung sichtbar machen

- `GatewayReadNotice`: bei `status === "degraded"` zusätzliche Klasse `gateway-read-degraded-banner` (Hintergrund), `data-gateway-read-status`, `data-degradation-reason`.
- `console.warn` in `api.ts` bei erfolgreichem JSON mit `status === "degraded"` (`[dashboard-api] gateway read degraded (HTTP ok)`), inkl. `degradation_reason` und `read_envelope_contract_version`.

---

## 6. Code-/Dateiänderungen (Umsetzung 30)

| Bereich        | Dateien                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Leser-Envelope | `services/api-gateway/src/api_gateway/gateway_read_envelope.py` — `read_envelope_contract_version`                       |
| HTTP-Fehler    | `services/api-gateway/src/api_gateway/errors.py` — `layer` im `error`-Objekt; 422 in `map_status_to_code`                |
| App            | `services/api-gateway/src/api_gateway/app.py` — 422 via `http_error_envelope`; 500 JSON erweitert; CORS `expose_headers` |
| BFF-Proxy      | `apps/dashboard/.../gateway/[...segments]/route.ts` + `gateway-read-response-headers.ts`                                 |
| Client         | `apps/dashboard/src/lib/api-fetch-errors.ts`, `api.ts`                                                                   |
| Typen          | `shared/ts/src/gatewayReadEnvelope.ts`                                                                                   |
| UI             | `GatewayReadNotice.tsx`, `globals.css`                                                                                   |

---

## 7. Nachweise

### 7.1 Jest (Dashboard)

- `pnpm test -- gateway-read-response-headers`
- `pnpm test -- api-fetch-errors`
- `pnpm test -- paper-read-notice` (GatewayReadNotice)

### 7.2 Pytest

- `python -m pytest tests/unit/api_gateway/test_gateway_read_envelope.py -q`

### 7.3 Typecheck

- Repo-Root: `pnpm check-types`

**Ergebnis (lokal, 2026-04-05):**

- Pytest `test_gateway_read_envelope.py`: **3 passed**
- Jest (gateway-read-response-headers, api-fetch-errors, paper-read-notice): **11 passed** / 3 Suites
- `pnpm check-types`: **Turbo** — `shared-ts` + `dashboard` **erfolgreich**

---

## 8. Offene Punkte

- **[FUTURE]** GET-Allowlist oder Pfad-Tags im Gateway, um `degradation_reason` stärker zu normieren.
- **[FUTURE]** Redundante Doppelqueries (z. B. Facets + Recent) gezielt zusammenlegen — nicht Teil dieses Schritts.
- **[TECHNICAL_DEBT]** Nicht-GET unhandled 500 könnte langfristig dasselbe `error`-Envelope wie HTTPException nutzen.
