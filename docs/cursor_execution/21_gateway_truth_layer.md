# 21 — Gateway als Wahrheitsschicht: `/ready` und `/v1/system/health`

## Ziel

Eine **stabile, gemeinsame Wahrheit** fuer **Operatoren**, **Monitoring** und **Dashboard**: harte technische Readiness am Edge, daneben eine **erklaerte, typisierte Aggregation** mit klarer Auth. Bezug: **Datei 02** (`docs/chatgpt_handoff/02_SYSTEM_TOPOLOGIE_UND_SERVICES.md`), **Datei 04** (`docs/chatgpt_handoff/04_API_BFF_ENDPOINT_DOSSIER.md`).

## Rollen der Endpunkte

| Endpunkt                | Rolle                                                                                         | Auth                              | HTTP                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------- |
| `GET /health`           | **Liveness** — Prozess/ASGI lebt                                                              | keine                             | 200 + `{ status, service, role: liveness }`              |
| `GET /ready`            | **Readiness** — Postgres, Schema/Migrations-Katalog, Redis, optional `READINESS_REQUIRE_URLS` | keine                             | 200; `ready` ist **bool** (false ist wahrheitsgemaess)   |
| `GET /v1/system/health` | **Operator-Aggregat** — Frische, Worker-Sonden, Ops, Warnungen, `aggregate.level`             | `require_operator_aggregate_auth` | 200 JSON; Fehlerauth **401** mit strukturiertem `detail` |

## Vertrag `GET /ready`

- **`readiness_contract_version`:** aktuell `1` (Feld im JSON).
- **`ready`:** logisches UND aller Checks in `checks` (Kern + optionale `upstream_*`).
- **Kern-Checks** (identisch zu `readiness_core.checks` in System-Health, **ohne** Peers): `postgres`, `postgres_schema`, `redis`.
- Implementierung: `api_gateway.gateway_readiness_core.gateway_readiness_core_parts_raw()` + `append_peer_readiness_checks` in `app.py`.

## Vertrag `GET /v1/system/health`

Neu bzw. fokussiert stabilisiert:

- **`truth_layer`:** Metadaten (`schema_version`), Semantik deutsch, Pfade, **Auth-Hinweis**, Verweis auf `/ready`.
- **`aggregate`:** `level` ∈ `green` | `degraded` | `red`, `summary_de`, `primary_reason_codes`.
  - **red:** `readiness_core.ok` ist false (Kern wie `/ready` ohne Peers).
  - **degraded:** Kern ok, aber `warnings` nicht leer **oder** mindestens eine **konfigurierte** Service-Sonde mit `status` `error`/`degraded`.
  - **green:** Kern ok, keine Warnungen, alle konfigurierten Sonden ohne Fehler (`not_configured` zaehlt nicht negativ).
- **`readiness_core`:** `ok`, `checks` (Kern), `contract_version`, operative Labels `database` / `redis` (Schema- bzw. Stream-Sonde), `note`.

**Auth:** `require_operator_aggregate_auth` — bei erzwungener sensibler Auth: JWT mit `gateway:read` oder `admin:read`, alternativ `X-Gateway-Internal-Key` mit passender Rolle; in nicht-produktiven Setups kann erzwungene Auth aus sein (siehe Settings).

**BFF:** Dashboard nutzt `DASHBOARD_GATEWAY_AUTHORIZATION` und typisch `/api/dashboard/gateway/v1/system/health` (siehe Datei 04). `runGatewayBootstrapProbe` prueft `/health`, `/ready`, dann `/v1/system/health` — Reihenfolge und Fehlercodes bleiben die massgebliche Kette.

## Beispielpayloads (schematisch)

### `/health` (immer aehnlich)

```json
{
  "status": "ok",
  "service": "api-gateway",
  "role": "liveness"
}
```

### `/ready` — kern-gruen, ohne Peers

```json
{
  "ready": true,
  "role": "readiness",
  "service": "api-gateway",
  "readiness_contract_version": 1,
  "checks": {
    "postgres": { "ok": true, "detail": "ok" },
    "postgres_schema": { "ok": true, "detail": "ok" },
    "redis": { "ok": true, "detail": "ok" }
  },
  "summary": {
    "core_postgres_connect": true,
    "core_postgres_schema": true,
    "core_redis": true,
    "peer_checks_configured": 0
  }
}
```

### `/ready` — rot (fehlende DSN)

```json
{
  "ready": false,
  "readiness_contract_version": 1,
  "checks": {
    "postgres": {
      "ok": false,
      "detail": "missing database DSN (DATABASE_URL*)"
    },
    "postgres_schema": {
      "ok": false,
      "detail": "no DATABASE_URL / DATABASE_URL_DOCKER — postgres_schema not evaluated"
    },
    "redis": { "ok": false, "detail": "missing REDIS_URL / REDIS_URL_DOCKER" }
  },
  "summary": {
    "core_postgres_connect": false,
    "core_postgres_schema": false,
    "core_redis": false,
    "peer_checks_configured": 0
  }
}
```

### `/v1/system/health` — aggregate green (Auszug)

```json
{
  "server_ts_ms": 1743868800000,
  "symbol": "BTCUSDT",
  "truth_layer": {
    "schema_version": 1,
    "readiness": { "path": "/ready", "contract_version": 1 },
    "system_health": { "path": "/v1/system/health", "contract_version": 1 }
  },
  "aggregate": {
    "level": "green",
    "summary_de": "Kern-Readiness ok, keine aktiven Warnungen, konfigurierte Sonden ohne Fehler.",
    "primary_reason_codes": []
  },
  "readiness_core": {
    "ok": true,
    "database": "ok",
    "redis": "ok",
    "contract_version": 1,
    "checks": {
      "postgres": { "ok": true, "detail": "ok" },
      "postgres_schema": { "ok": true, "detail": "ok" },
      "redis": { "ok": true, "detail": "ok" }
    },
    "note": null
  },
  "warnings": [],
  "warnings_display": [],
  "services": [],
  "ops": {},
  "data_freshness": {}
}
```

### `/v1/system/health` — degraded (Warnung)

`aggregate.level` = `degraded`, `primary_reason_codes` enthaelt z. B. `stale_signals`, `warnings_display` liefert Texte aus `shared_py.health_warnings_display`.

### `/v1/system/health` — rot (Kern)

`readiness_core.ok` false, `aggregate.level` = `red`, `primary_reason_codes` enthaelt `readiness_core_failed`.

## Nachweise (Kommandos)

```bash
curl -sS "$API_GATEWAY_URL/health"
curl -sS "$API_GATEWAY_URL/ready" | jq .
curl -sS -H "Authorization: Bearer <JWT>" "$API_GATEWAY_URL/v1/system/health" | jq '.aggregate,.readiness_core,.truth_layer'
```

**Tests (Auswahl):**

```bash
pytest tests/unit/api_gateway/test_gateway_ready_contract.py tests/unit/api_gateway/test_gateway_truth_layer.py -q
```

## Code-Pfade

- `services/api-gateway/src/api_gateway/gateway_readiness_core.py` — gemeinsamer Kern fuer `/ready` und System-Health.
- `services/api-gateway/src/api_gateway/system_health_truth_layer.py` — `aggregate`, `truth_layer` Metadaten.
- `services/api-gateway/src/api_gateway/routes_system_health.py` — `compute_system_health_payload`.
- `services/api-gateway/src/api_gateway/app.py` — `/health`, `/ready`.
- `apps/dashboard/src/lib/types.ts` — TypeScript-Typen `SystemHealthAggregate`, `truth_layer`, `readiness_core`.
- `apps/dashboard/src/lib/gateway-bootstrap-probe.ts` — Bootstrap-Kette inkl. System-Health.

## Offene Punkte

- `[FUTURE]` **edge-status** BFF: optional `aggregate.level` aus System-Health in der JSON-Antwort spiegeln (derzeit nur implizit ueber erfolgreichen Probe-Lauf).
- `[TECHNICAL_DEBT]` Vollparität **OpenAPI** `shared/contracts/openapi/api-gateway.openapi.json` mit neuen Feldern — bei Bedarf nachziehen.
