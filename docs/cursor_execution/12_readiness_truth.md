# 12 — Readiness- und Health-Wahrheit (Gateway & Stack)

**Grundlage:** `docs/chatgpt_handoff/02_SYSTEM_TOPOLOGIE_UND_SERVICES.md`, `03_ENV_SECRETS_AUTH_MATRIX.md`, `08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md`  
**Stand:** 2026-04-05

---

## 1. Begriffe (verbindlich)

| Endpoint / Signal               | Rolle                 | Kern-Regel                                                                                                                                                                                                                                                                                      |
| ------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`GET /health`** (api-gateway) | **Liveness**          | Prozess/ASGI antwortet. **Keine** Postgres-/Redis-Prüfung. Immer `status: ok`, solange der Server läuft.                                                                                                                                                                                        |
| **`GET /ready`** (api-gateway)  | **Readiness (Kern)**  | `ready: true` **nur**, wenn Postgres-Verbindung, **Schema/Migrationen** (Kern-Tabellen + kein pending laut Katalog `infra/migrations/postgres/`) und Redis **grün** sind, plus alle konfigurierten **Peer-URLs** (`READINESS_REQUIRE_URLS`) grün.                                               |
| **`GET /v1/system/health`**     | **Operator-Aggregat** | Erfordert **Operator-JWT** (siehe Auth-Matrix). Kombiniert DB-Schema, Redis/Streams, Freshness, Service-Probes (`HEALTH_URL_*`), Ops-Summary. **Kein** Ersatz für `/ready`; Kern-Datastore schlecht → `readiness_core.ok: false` und `services` mit `api-gateway`-Eintrag **nicht** blind `ok`. |
| **Compose-`healthcheck`**       | Orchestrierung        | Pro Service: typisch HTTP `/ready` oder `/health`. Gateway-Compose prüft JSON-Feld `ready === true`.                                                                                                                                                                                            |

---

## 2. Gateway `/ready` — Payload-Regeln

- **`checks`**: immer vorhanden (auch `PRODUCTION=true`). Jeder Eintrag: `{ "ok": bool, "detail": string }`.
- **`summary`**: kompakte Booleans (`core_postgres_connect`, `core_postgres_schema`, `core_redis`, `peer_checks_configured`).
- **`role`**: `"readiness"`, **`service`**: `"api-gateway"`.
- **DSN-Auflösung:** `effective_database_dsn` / `effective_redis_url` — `DATABASE_URL` bzw. `REDIS_URL`, sonst Fallback `*_DOCKER` (analog zu Laufzeit-DSN).
- **Kein Schein-Grün bei fehlender DSN:** Fehlen beide DB-Strings, ist `postgres_schema.ok` **false** (nicht mehr „skipped“ als wahr).
- **HTTP-Status:** weiterhin **200** mit `ready: false` bei Fehlern (Compose-/Skripte lesen JSON). Tiefere HTTP-Semantik (z. B. 503) wäre ein gesondertes Migrationsprojekt für alle Probes (`check_http_ready_json` kann JSON bei HTTP-Fehler bereits parsieren).

### 2.1 Beispiel `GET /ready` (alle Kern-Checks grün, keine Peers)

```json
{
  "ready": true,
  "role": "readiness",
  "service": "api-gateway",
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
  },
  "app_env": "local"
}
```

(`app_env` nur wenn `PRODUCTION=false`.)

### 2.2 Beispiel `GET /ready` (Schema nicht ok)

```json
{
  "ready": false,
  "role": "readiness",
  "service": "api-gateway",
  "checks": {
    "postgres": { "ok": true, "detail": "ok" },
    "postgres_schema": {
      "ok": false,
      "detail": "pending_migrations=2 (first: 090_x.sql, …) — run: python infra/migrate.py (DATABASE_URL)"
    },
    "redis": { "ok": true, "detail": "ok" }
  },
  "summary": {
    "core_postgres_connect": true,
    "core_postgres_schema": false,
    "core_redis": true,
    "peer_checks_configured": 0
  }
}
```

---

## 3. Gateway `/health` — Beispiel

```json
{
  "status": "ok",
  "service": "api-gateway",
  "role": "liveness"
}
```

---

## 4. `GET /v1/system/health` — Ergänzungen

- Neues Feld **`readiness_core`**: `{ "ok": bool, "database": "ok"|"error", "redis": "ok"|"error"|"skipped", "note": string|null }`.
- **`services`-Eintrag `api-gateway`:** `status` ist **`error`**, wenn DB oder Redis (Kern) nicht `ok` — nicht mehr fest `ok` mit `note: self`.

Freshness-Warnungen, Provider-Hints und Worker-Probes bleiben **degradierte Teilpfade**; sie dürfen das aggregierte Payload informativ reich halten, ersetzen aber **nicht** den Kern-Readiness-Contract von `/ready`.

---

## 5. Peer-Readiness (`READINESS_REQUIRE_URLS`)

- **Gateway (Basis-Compose):** oft **nicht** gesetzt — Abhängigkeiten primär über Compose `depends_on`. Wenn gesetzt, erscheinen Checks als `upstream_0`, `upstream_1`, … in `/ready` und `merge_ready_details` verknüpft sie per **UND** mit dem Kern.
- **Worker:** kommagetrennte `/ready`-URLs; Probes nutzen `shared_py.observability.health.check_http_ready_json` (inkl. Lesen von JSON bei HTTP-Fehlerantworten mit Fehlerdetails).

---

## 6. Nachweise (CI / lokal)

**Ausgeführt (2026-04-05, Repo-Root):**

- `python -m pytest tests/unit/api_gateway/test_gateway_ready_contract.py -q` → **3 passed**
- `python -m pytest tests/unit/shared_py/test_readiness_probe_http.py -q` → **2 passed**

**Laufzeit-HTTP** (`GET http://127.0.0.1:8000/health`, `/ready`, `/v1/system/health` mit JWT): in der Erstellungssitzung kein erreichbarer Gateway-Prozess (Timeout) — nach `pnpm dev:up` / Compose erneut ausführen.

---

## 7. Betriebs-Hinweise

- Bei **`ready: false`**: zuerst `checks.postgres`, `checks.postgres_schema`, `checks.redis`, dann `upstream_*`.
- **`/health` grün bei rotem `/ready`** ist **erwartet** (Liveness vs. Readiness).
- Operator-Sicht: **`/v1/system/health`** + **`readiness_core`** + Spalte **`services`** (api-gateway).

---

## 8. Offene Punkte

- `[FUTURE]` Optional einheitlich **HTTP 503** bei `ready: false` nachziehen, sobald alle Clients (Compose-`healthcheck`, `scripts/healthcheck.sh`, externe LB) Body bei Nicht-200 zuverlässig lesen.
