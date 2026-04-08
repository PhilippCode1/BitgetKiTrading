# Produktionsreife: API-Vertraege, Zahlungen, Evidenz

Dieses Dokument schliesst die Luecke aus **PROMPT 25** (fehlende Beispiel-Payloads und klare Sandbox/Live-Zuordnung). Es ersetzt keine Live-Logs — Betreiber haengen weiterhin `docker compose ps`, Gateway-Logs und Screenshots an.

## Health-Warnungen: `warnings_display[].machine` (KI / Automation)

Ab Schema **`health-warning-machine-v1`** enthaelt jeder Eintrag in `warnings_display` zusaetzlich:

- `summary_en` — kompakte Problembeschreibung auf Englisch (fuer LLM-Ingest)
- `problem_id` — stabiler Identifier (z. B. `health.ops_alerts_open`)
- `severity` — `info` | `warn` | `critical`
- `facts` — u. a. `warning_code`, Ops-Zaehler (`open_alert_count`, …)
- `suggested_actions` — typisierte Schritte (`http_inspect`, `env_optional`, `sql_reference`, `compose_logs`, …)
- `verify_commands` — Shell-/curl-Vorschlaege mit Platzhaltern (`$API_GATEWAY_URL`)

Das Dashboard klappt das unter **„Maschinenlesbar (KI / Automation)“** auf und zeigt das JSON vollstaendig.

## Leser-Envelope (fast alle `/v1/...`-DB-Reads)

Gateway nutzt `merge_read_envelope` (`services/api-gateway/src/api_gateway/gateway_read_envelope.py`):

| Feld                 | Bedeutung                               |
| -------------------- | --------------------------------------- |
| `status`             | `ok` \| `empty` \| `degraded`           |
| `message`            | Kurzer deutscher Nutzertext oder `null` |
| `empty_state`        | `true` wenn fachlich „leer“             |
| `degradation_reason` | Maschinencode oder `null`               |
| `next_step`          | Konkrete Handlung oder `null`           |

Die fachliche Nutzlast liegt **zusaetzlich** in denselben Keys (z. B. `items`, `item`, `limit`).

## Kernendpunkte: Beispiel-JSON

### GET `/v1/monitor/alerts/open`

Offene Alerts aus `ops.alerts`. HTTP 200 auch bei leerer Liste.

```json
{
  "items": [
    {
      "alert_key": "data_stale_candles",
      "severity": "warning",
      "title": "Candles stale",
      "message": "No candle close in window",
      "details": {},
      "state": "open",
      "created_ts": "2026-03-31T12:00:00+00:00",
      "updated_ts": "2026-03-31T12:05:00+00:00"
    }
  ],
  "limit": 50,
  "status": "ok",
  "message": null,
  "empty_state": false,
  "degradation_reason": null,
  "next_step": null
}
```

Leer (ok, empty_state true):

```json
{
  "items": [],
  "limit": 50,
  "status": "ok",
  "message": "Keine offenen Monitor-Alerts.",
  "empty_state": true,
  "degradation_reason": "no_open_alerts",
  "next_step": null
}
```

### GET `/v1/learning/drift/online-state`

Kombination aus `gateway_online_drift_state_response` + Envelope. Zeile aus `learn.online_drift_state` oder `item: null`.

Mit Zeile:

```json
{
  "status": "ok",
  "item": {
    "scope": "global",
    "effective_action": "ok",
    "computed_at": "2026-03-31T11:00:00+00:00",
    "lookback_minutes": 60,
    "breakdown_json": {}
  },
  "seeded": false,
  "message": null,
  "empty_state": false,
  "degradation_reason": null,
  "next_step": null
}
```

Ohne Zeile (weiterhin HTTP 200, fachlich leer):

```json
{
  "status": "ok",
  "item": null,
  "detail": null,
  "seeded": false,
  "message": "Kein materialisierter Online-Drift-State (Zeile fehlt).",
  "empty_state": true,
  "degradation_reason": "no_online_drift_row",
  "next_step": "Migration 400 und POST /learning/drift/evaluate-now auf der Learning-Engine ausfuehren."
}
```

### GET `/v1/learning/metrics/strategies`

Strategie-Metriken mit festem `limit` (Page-Size, cap 200) — gleiches Listen-Envelope wie andere `/v1/learning/*`-Reads (`items`, `limit`, `status`, `message`, `empty_state`, `degradation_reason`, `next_step`).

### GET `/v1/learning/models/registry-v2`

`limit` ist die angefragte Obergrenze (nicht die Zeilenzahl); bei Degrade gleicher `limit`-Wert wie im Erfolgsfall.

### GET `/v1/learning/recommendations/recent`

Wie Metriken: `items` + `limit` + Leser-Envelope.

### GET `/v1/learning/drift/recent`

Events aus `learn.drift_events`.

```json
{
  "status": "ok",
  "items": [
    {
      "drift_id": "550e8400-e29b-41d4-a716-446655440000",
      "metric_name": "psi_features",
      "severity": "warn",
      "details_json": {},
      "detected_ts": "2026-03-30T10:00:00+00:00"
    }
  ],
  "limit": 50,
  "seeded": false,
  "message": null,
  "empty_state": false,
  "degradation_reason": null,
  "next_step": null
}
```

## Zahlungen: Sandbox vs. produktiv

Quelle der Wahrheit im Code: `config/gateway_settings.py` (`payment_mode`, `payment_*`) und `api_gateway.payments.capabilities.build_payment_capabilities`.

| Modus                | ENV (Auszug)                                                                   | Stripe echt                                                                                                         | Mock-Provider                                                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sandbox**          | `PAYMENT_MODE=sandbox` (oder nicht `live`)                                     | Nur wenn `PAYMENT_STRIPE_ENABLED`, Secret gesetzt; Webhook-Secret in Live-Pflicht entfaellt in reinem Sandbox-Check | Moeglich wenn `PAYMENT_MOCK_ENABLED` + `PAYMENT_MOCK_WEBHOOK_SECRET` (nicht in `PRODUCTION` ohne Ausnahme — siehe `build_payment_capabilities`) |
| **Live / produktiv** | `PAYMENT_MODE=live`, `PRODUCTION=true`, `PAYMENT_MOCK_ENABLED=false` empfohlen | `PAYMENT_STRIPE_WEBHOOK_SECRET` **Pflicht** wenn Stripe aktiv                                                       | Mock typisch **aus**                                                                                                                            |

**UI:** Dashboard-Einzahlungsseite zeigt die Umgebung aus `GET .../payments/capabilities` (`environment`: `sandbox` \| `live`).

**Operator:** Vollstaendige Ablaufbeschreibung: `docs/payment_architecture.md`.

## GET `/v1/meta/surface` (oeffentlich, keine Auth)

Kompakte Laufzeit-Kontur fuer Freigaben und Dashboard-Chips — **keine Secrets**.

```json
{
  "schema_version": "public-surface-v1",
  "app_env": "local",
  "production": false,
  "execution": {
    "execution_mode": "paper",
    "strategy_execution_mode": "manual",
    "paper_path_active": true,
    "shadow_trade_enable": false,
    "live_trade_enable": false,
    "live_broker_enabled": false
  },
  "auth": {
    "sensitive_auth_enforced": false,
    "gateway_auth_credentials_configured": true
  },
  "commerce": {
    "commercial_enabled": false,
    "payment_checkout_enabled": false,
    "payment_environment": "sandbox",
    "telegram_bot_username_configured": false,
    "telegram_required_for_console": false
  },
  "endpoints": {
    "openapi": "/docs",
    "health": "/health",
    "ready": "/ready",
    "deploy_edge_readiness": "/v1/deploy/edge-readiness",
    "public_surface": "/v1/meta/surface"
  }
}
```

## Evidenz sammeln (ohne manuelle Sondergriffe)

1. Stack: `docs/LOCAL_RELEASE_CANDIDATE.md`
2. **Dump-Ordner (Windows):** `pnpm run rc:evidence` → `artifacts/release-evidence/<timestamp>/` (`compose_ps.txt`, `meta_surface.json`, `rc_health_edge.stdout.txt`, …)
3. Automatisierte Edge-Checks: `pnpm run rc:health` — prueft u. a. `/v1/meta/surface`, `/v1/deploy/edge-readiness`, Drift, Monitor, Live-State
4. Aggregiert: `GET /v1/system/health` (mit Auth, wenn `GATEWAY_ENFORCE_SENSITIVE_AUTH=true`)

## Auth-Hinweis

Lokal oft `GATEWAY_ENFORCE_SENSITIVE_AUTH=false`. In **Produktion** JWT und/oder interner API-Key erzwingen — `docs/api_gateway_security.md`.
