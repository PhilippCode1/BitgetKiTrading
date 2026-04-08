# Fehler, Alerts und Root Cause (bitget-btc-ai)

**Zweck:** ChatGPT soll nach dem Lesen **konkret** wissen, warum die App im Alltag ausfällt, Alerts erzeugt, leere oder alte Daten zeigt oder Einzelfunktionen scheitert — mit Trennung **Ursache / Symptom / Verdacht**.

**Legende**

- **Ursache (technisch):** nachweislich oder sehr wahrscheinlich aus Architektur/Code.
- **Symptom:** was Nutzer oder Ops sehen — **keine** Ursache an sich.
- **Verdacht:** mögliche Erklärung ohne Codebeweis für den konkreten Vorfall.

**Kennzeichnung:** `verifiziert (Repo)` = aus diesem Repository ableitbar; `nicht verifiziert (Fall)` = braucht Logs/Tickets zum Einzelfall.

---

## 1. Zusammenfassung der Top-Ursachen

1. **Edge nicht erreichbar oder falsch konfiguriert:** `API_GATEWAY_URL` fehlt/falsch, Gateway-Container down, TLS/Proxy falsch → **gesamte** Konsole über BFF tot (503, Fetch-Fehler). **Symptom** wirkt wie „App kaputt“, **Ursache** ist fast immer **Netz/ENV**, nicht „ein Button“.

2. **Dashboard-Server ohne gültiges Gateway-JWT:** `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt/abgelaufen/falsch → **503** auf praktisch allen `/api/dashboard/*`-Proxys. **Ursache:** Betriebs-Setup, nicht Browser-Cache.

3. **Postgres oder Redis weg oder Schema nicht migriert:** Gateway-Queries scheitern → leere Tabellen, `health.db=error`, System-Health degradiert. **Ursache:** Infra oder vergessene Migrationen.

4. **Pipeline-Produzent aus:** `market-stream` oder nachgelagerte Engines laufen nicht → **keine/neue** Kerzen/Signale/Features; UI zeigt leere Charts oder alte Bars; Monitor meldet **Datenfrische** oder **Stream stalled**. **Ursache:** Prozess/Startreihenfolge/Readiness-Kette (`READINESS_REQUIRE_URLS`), nicht „Chart-Bug“.

5. **Bitget/Provider-seitig:** Credentials unvollständig, Rate-Limit (429), WS-Disconnect → Ingest stockt; Health zeigt `provider:*`-Codes. **Ursache:** Exchange/Keys/Netz laut `PROVIDER_ERROR_SURFACES.md`.

6. **LLM-Strecke:** Orchestrator down, `INTERNAL_API_KEY` ≠ Gateway, `OPENAI_API_KEY` fehlt bei Fake=false, Timeouts → 502/503 und UI-Fehlertexte. **Ursache:** Konfiguration oder Upstream-Quota, nicht „KI will nicht“.

7. **SSE absichtlich oder faktisch aus:** `LIVE_SSE_ENABLED=false` oder `REDIS_URL` leer am Gateway → Stream-Endpoint **503**; Terminal fällt auf Polling zurück — **Symptom** „kein Live-Gefühl“, **Ursache** oft Konfiguration.

8. **Monitor-Engine erzeugt erwartungsgemäß Alerts:** Scheduler sieht schlechte Service-Probes, Redis-Stream-Lag, **stale** Datenpunkte oder **stagnierende** Stream-Länge bei kritischer Kerze → `ops.alerts` + `events:system_alert`. **Ursache:** oft **echtes** Betriebsproblem, nicht „falsches Alerting“.

---

## 2. Fehlerklassen mit Priorität P0 / P1 / P2

### P0 — Gesamtsystem oder Sicherheit / Live-Risiko

| Klasse   | Kurzbeschreibung                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **P0-A** | Gateway nicht erreichbar oder `DATABASE_URL`/`REDIS_URL` am Gateway ungültig                               |
| **P0-B** | Dashboard BFF ohne `API_GATEWAY_URL` oder ohne gültiges `DASHBOARD_GATEWAY_AUTHORIZATION`                  |
| **P0-C** | Postgres nicht erreichbar oder Migrationen fehlen (Schema-Fehler in Logs)                                  |
| **P0-D** | Kill-Switch / Safety-Latch aktiv wo nicht beabsichtigt (Live blockiert) — **Verdacht** bis Journal geprüft |

### P1 — Kernfunktionen beeinträchtigt (Daten, Streaming, LLM, Alerts)

| Klasse   | Kurzbeschreibung                                                           |
| -------- | -------------------------------------------------------------------------- |
| **P1-A** | `market-stream` down oder Bitget-Feed unterbrochen                         |
| **P1-B** | Redis down oder Streams mit hohem Lag/Pending (Consumer krank)             |
| **P1-C** | Einzelne Engines down (feature/signal/paper/…) → Teilpfad leer             |
| **P1-D** | LLM-Orchestrator unreachable / Key-Mismatch / OpenAI fehlt                 |
| **P1-E** | SSE deaktiviert oder Redis für SSE fehlt                                   |
| **P1-F** | Monitor-Engine meldet Freshness/Service/Stream-Alerts (Ops muss reagieren) |

### P2 — Degradierung, UX, Einzelfälle, Tooling

| Klasse   | Kurzbeschreibung                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **P2-A** | Facets/Statistik-Endpoint fehlgeschlagen — Filter bleiben nutzbar                                                                           |
| **P2-B** | Demo-Seeds (postgres_demo + Fixture-ENV) — können „Daten da“ vortäuschen; UI-Hinweis `demo_data_notice`, Vertrag Doku **11**                |
| **P2-C** | CI/lokale Skripte (PowerShell-Encoding, fehlendes `.env.local`) — **Symptom** „Smoke schlägt fehl“, **Ursache** oft Host, nicht Produktcode |
| **P2-D** | Einzelne UI-Bugs oder fehlende i18n — kein Infra-Notfall                                                                                    |

---

## 3. Tabelle: Ursache, Symptom, Nachweis, Fix

| Priorität | Ursache (technisch)                                       | Symptom UI                                                 | Symptom Gateway / BFF                                  | Symptom Dienst                         | Nachweis (Repo/Ops)                                   | Fix-Strategie                                            |
| --------- | --------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| P0        | `API_GATEWAY_URL` falsch/fehlt (Dashboard-Server)         | Konsole: Fetch-Hinweise, Bootstrap-Banner                  | BFF 503, `edge-status` schlecht                        | —                                      | `edge-status`, `gateway-bootstrap-probe.ts`           | Korrekte ENV, Gateway erreichbar, Dev-Server neu starten |
| P0        | JWT `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt/ungültig      | Gleiches                                                   | **503** mit klarer `detail`, `operatorHealthProbe` rot | Gateway kann ok sein                   | `GET /api/dashboard/edge-status`, Mint-Skript in Doku | JWT neu minten, Secret/Claims prüfen                     |
| P0        | `DATABASE_URL` Gateway falsch/leer                        | Leere Daten, „Konfiguration“-artige Fetch-Maps             | DB-Health fail, Queries exception                      | Worker evtl. ebenfalls down            | Gateway-Logs, `get_database_url`                      | Postgres-URL, Netz, Credentials                          |
| P0        | Migrationen nicht angewendet                              | 500/Degraded, SQL-Fehler in Logs                           | `database_error` in Envelopes                          | Worker crash beim Start                | Migrations-Job, Logs                                  | `infra/migrate.py` / Compose-Migrationspfad              |
| P1        | `market-stream` nicht verbunden / Bitget-Ausfall          | Chart leer/stale, `market_freshness` stale/dead            | `/v1/live/state` ohne neue Kerzen                      | WS reconnect loops, 429 in Logs        | market-stream Logs, `provider_ops_summary`            | Bitget-Keys, Netz, Rate-Limits; Dienst neu starten       |
| P1        | `feature-engine` / `signal-engine` aus                    | `latest_feature`/`latest_signal` null, data_lineage „leer“ | DB-Queries liefern nichts Neues                        | `/ready` not ok                        | `stack_readiness.md`, Service-Logs                    | Startreihenfolge, `READINESS_REQUIRE_URLS`, Redis/DB     |
| P1        | Redis weg                                                 | SSE 503, Stream-Consumer stoppen                           | `health.redis=error`, SSE detail                       | Alle Redis-User                        | Gateway health, `routes_live.py`                      | Redis-Container, `REDIS_URL` konsistent                  |
| P1        | `LIVE_SSE_ENABLED=false`                                  | Terminal ohne Push-Gefühl                                  | **503** auf `/v1/live/stream` mit explizitem Detail    | —                                      | `routes_live.py`                                      | ENV auf true **oder** Polling akzeptieren                |
| P1        | LLM: Orchestrator down                                    | KI-Panels: 502/503, lange Timeouts                         | Gateway `LLM_ORCH_UNAVAILABLE` / 502                   | Orchestrator health rot                | `ai-architecture.md`, Gateway-Logs                    | Stack, `INTERNAL_API_KEY`, `LLM_ORCH_BASE_URL`           |
| P1        | LLM: OpenAI fehlt, Fake aus                               | Nutzer sieht OpenAI-Key-Fehler über 502                    | Forward-Fehler vom Orchestrator                        | Orchestrator health `llm_provider_gap` | Orchestrator-ENV                                      | Key setzen oder Fake nur lokal                           |
| P1        | `INTERNAL_API_KEY` mismatch                               | 401/403/502 je nach Pfad                                   | Orchestrator lehnt intern ab                           | Orchestrator logs                      | Zwei ENV vergleichen                                  | Gleichen Key setzen                                      |
| P1        | Monitor: Datenfrische überschritten                       | Health-Warnungen, Alert-Liste in UI                        | `fetch_data_freshness` + warnings                      | `monitor_engine` specs                 | `alerts_from_freshness`, `ops.alerts`                 | Ursachen-Pipeline reparieren, nicht Alert unterdrücken   |
| P1        | Monitor: Redis-Stream-Lag                                 | Alerts „Redis Stream belastet“                             | Metriken / DB alerts                                   | Consumer-Gruppe backlog                | `alerts_from_stream_checks`                           | Consumer health, `XPENDING`, Engpass beseitigen          |
| P1        | Monitor: Stream-Länge stagniert + 1m-Kerze kritisch stale | Critical Alert „Stream wächst nicht…“                      | —                                                      | Stream length + candle check           | `alert_stream_stalled`, `loop.py`                     | market-stream + Bitget + Redis                           |
| P2        | Facets-Endpoint Fehler                                    | Signalseite: Hinweis, Tabelle evtl. ok                     | Einzelner Call failed                                  | —                                      | `facetsFallback` in `de.json`                         | Backend prüfen, vereinzelter Bug                         |
| P2        | Nur Demo-Daten in frischer DB                             | „Daten“ sichtbar, aber nicht Live                          | —                                                      | postgres_demo / Fixture-ENV            | `11_migrations_and_seed_separation.md`                | Live-Pipeline prüfen; Banner `demo_data_notice`          |
| P2        | Windows/PowerShell Smoke-Encoding                         | Script bricht mit ParserError                              | —                                                      | —                                      | Bekannt aus `05`/Skript-Issues                        | Skript-Encoding reparieren oder WSL                      |

---

## 4. Warum Alerts aktuell entstehen können

**Ursache (technisch, `verifiziert (Repo)`):** Die `monitor-engine` führt periodisch HTTP-Probes, Redis-Stream-Gruppen-Checks und SQL-Datenfrische aus. Jede Abweichung erzeugt `AlertSpec`-Einträge; `process_alerts` schreibt nach **`ops.alerts`** und veröffentlicht **`events:system_alert`** (Dedupe).

**Konkrete Trigger:**

- **Service-Check nicht ok/degraded** → Alert-Key `svc:<name>:<check>` (z. B. live-broker kill_switch, reconcile, shadow_live_divergence).
- **Stream-Gruppe** mit Pending/Lag → `stream:<stream>:group:<group>`.
- **Freshness-Row** nicht ok → `freshness:<datapoint>`.
- **Stream-Länge unverändert** bei **kritischer** 1m-Kerzen-Stale → `stream_stalled:<stream>` (critical, hohe Priorität).

**Symptom in der Oberfläche:** Konsole Health/Ops zeigt **offene Monitor-Alerts** und ggf. **warnings** im aggregierten System-Health.

**Fehlinterpretation (Symptom vs. Ursache):** „Zu viele Alerts“ ist **Symptom** — **Ursache** ist fast immer **defekte Pipeline oder Überlast**, nicht „Alerting zu empfindlich“ ohne Beweis.

---

## 5. Warum Daten leer oder veraltet sein können

| Ursache                                      | Symptom UI                                         | Gateway/SQL                                          |
| -------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------- |
| Keine Zeilen in `tsdb.candles` für Symbol/TF | Leerer Chart, `market_freshness` no_candles/stale  | `fetch_candles` leer                                 |
| `market-stream` schreibt nicht               | Gleiches                                           | Producer-Logs                                        |
| Falsches Symbol (nicht ingestiert)           | Leer                                               | Query leer (Symbol validiert Format, nicht Existenz) |
| Engines nicht gestartet                      | `latest_signal` null, data_lineage erklärt Segment | Joins leer                                           |
| DB-Fehler im `build_live_state`              | Frische-Block geleert, `health.db=error`           | Exception in Gateway                                 |
| Alte Kerzen, kein neuer Ingest               | Chart „eingefroren“, Banner stale/dead             | `compute_market_freshness_payload`                   |
| Demo-Migrationen / postgres_demo             | Daten „da“, aber nicht Bitget                      | Doku 11, `demo_data_notice` im Live-State            |

**Verdacht:** „Frontend cached falsch“ — **selten** Ursache; zuerst **Gateway-Response** und **DB** prüfen.

---

## 6. Warum KI-Funktionen scheitern können

| Ursache                                     | UI                                            | Gateway           | Orchestrator              |
| ------------------------------------------- | --------------------------------------------- | ----------------- | ------------------------- |
| Orchestrator nicht erreichbar               | 503 „Orchestrator…“ / generische Fetch-Fehler | 503 `LLM_ORCH_*`  | Prozess down              |
| `INTERNAL_API_KEY` falsch                   | 401/502                                       | Forward scheitert | 401 intern                |
| `OPENAI_API_KEY` fehlt bei Fake=false       | 502 mit Key-Hinweis                           | 502 Body          | Health `llm_provider_gap` |
| Timeout (langsames Modell)                  | Abbruch nach ~125 s                           | Timeout           | Upstream langsam          |
| Input zu groß/invalid                       | 413/422                                       | durchgereicht     | Validierung               |
| Redis am Orchestrator fehlt (Cache/Circuit) | Degradierung möglich                          | —                 | Health rot                |

**Symptom:** „KI antwortet nicht“ — **keine** Ursache; immer **Statuscode + edge-status + Orchestrator-Logs** lesen.

---

## 7. Warum Charts oder Strategie-Sichtbarkeit scheitern können

**Charts**

- **Ursache:** siehe Abschnitt 5 — Chart liest **`/v1/live/state`** → `tsdb.candles`.
- **Symptom:** leerer Chart trotz „alles grün“ → **Verdacht** falsches Symbol/TF oder Daten nur für anderes Universum.
- **Strategie-Signal-KI Chart-Layer:** zusätzlich: LLM-Antwort ohne gültige `chart_annotations` oder Layer aus — **Symptom** „keine Linien“, **Ursache** Modell-Output oder Sanitizer.

**Strategie-Registry**

- **Ursache:** `learn.strategies` leer oder DB-Fehler.
- **Symptom:** leere Tabelle — **nicht** „LLM weg“, Registry ist **eigenständiger** Lesepfad.

**Signale**

- **Ursache:** `signal-engine` nicht persistierend oder Filter zu eng.
- **Symptom:** leere Liste — unterscheide **Filter** vs. **Pipeline**.

---

## 8. Welche Probleme wahrscheinlich durch Verbindung oder ENV entstehen

- Falsche **`API_GATEWAY_URL`** (http vs https, Port, Docker-Hostname).
- Fehlendes oder abgelaufenes **`DASHBOARD_GATEWAY_AUTHORIZATION`**.
- Inkonsistente **`REDIS_URL`** / **`DATABASE_URL`** zwischen Diensten.
- **`INTERNAL_API_KEY`** nicht identisch Gateway ↔ Orchestrator.
- Bitget-Variablen unvollständig für gewählten Modus (`credentials_complete`, `gap_codes`).
- **`LIVE_SSE_ENABLED`**, **`LLM_ORCH_BASE_URL`** / **`HEALTH_URL_LLM_ORCHESTRATOR`**.
- Compose **ohne** published ports auf Workern (Shadow/Prod) → Healthchecks vom Host scheitern — **Symptom** „alles rot“, **Ursache** Netzmodell, nicht zwingend defekter Code (`docs/compose_runtime.md`).

---

## 9. Welche Probleme eher im Code selbst liegen

**Eher Code / Produktlogik (nach Ausschluss von ENV):**

- Validierungs- oder Mapping-Bugs in Gateway-Routen (422, falsche Envelopes).
- Race oder Fehler in **einzelnen** Engines (Exceptions in Logs).
- Dashboard: falscher Pfad im BFF, fehlende Header — **aber** meist durch Tests abgedeckt für LLM-Routen.
- Migration-SQL-Fehler nach Schema-Änderung.

**Nicht automatisch „Code-Bug“:**

- Leere Tabellen bei **korrekt laufender** Pipeline und leerem Markt-Universum.
- Alerts bei **echtem** Ausfall — gewolltes Verhalten.

**Verdacht:** „Flaky E2E“ — oft **Timing** oder **ENV in CI** (`PRODUCT_STATUS.md` erwähnt Gateway-ENV für volle `create_app`-Tests).

---

## 10. Übergabe an ChatGPT

**Arbeitsanweisung für Folgefragen:**

1. Zuerst **P0** ausschließen: Gateway erreichbar, JWT gesetzt, Postgres/Redis vom Gateway aus.
2. Dann **Datenpfad**: `market-stream` → `tsdb.candles` → `/v1/live/state`.
3. **Alerts** nie als Root ansehen — **immer** `details` / `alert_key` / zugehörigen Service.
4. **KI** immer: Orchestrator Health + Gateway-Forward + Key-Parität.
5. Trenne **`Symptom` in der UI** von **`Ursache`** — die UI humanisiert Fetch-Fehler (`translateFetchError`).

---

## 11. Anhang mit Dateipfaden, Logs, Kommandos und Fehlermeldungen

### 11.1 Zentrale Dateien

| Thema                            | Pfad                                                                                      |
| -------------------------------- | ----------------------------------------------------------------------------------------- |
| Fehler → Nutzertext (Dashboard)  | `apps/dashboard/src/lib/user-facing-fetch-error.ts`, `api-fetch-errors.ts`                |
| Fetch-Hinweis-Komponente         | `apps/dashboard/src/components/console/ConsoleFetchNotice.tsx`                            |
| Edge-Diagnose                    | `apps/dashboard/src/app/api/dashboard/edge-status/route.ts`, `gateway-bootstrap-probe.ts` |
| Live-State / Frische             | `services/api-gateway/src/api_gateway/db_live_queries.py`                                 |
| SSE 503 Texte                    | `services/api-gateway/src/api_gateway/routes_live.py` (`LIVE_SSE_ENABLED`, `REDIS_URL`)   |
| System-Health Aggregation        | `services/api-gateway/src/api_gateway/routes_system_health.py`                            |
| Monitor-Regeln                   | `services/monitor-engine/src/monitor_engine/alerts/rules.py`, `scheduler/loop.py`         |
| Alerts DB                        | `infra/migrations/postgres/240_ops_monitoring.sql` (`ops.alerts`)                         |
| Stack/Readiness                  | `docs/stack_readiness.md`, `scripts/healthcheck.sh`                                       |
| Provider/Bitget/LLM Fehlerbilder | `docs/PROVIDER_ERROR_SURFACES.md`, `docs/monitoring_runbook.md`                           |
| Datenpipeline leer               | `docs/data_pipeline_overview.md`                                                          |
| Observability                    | `docs/observability.md`, `infra/observability/prometheus-alerts.yml`                      |
| LLM-Fail Events                  | `services/llm-orchestrator/src/llm_orchestrator/events/llm_failed.py`                     |

### 11.2 Typische Log-Kontexte

```text
# Gateway
api_gateway.live / api_gateway.system_health / api_gateway.routes_llm_operator

# Marktdaten
market_stream (WS reconnect, provider_http_status, orderbook_checksum_mismatch)

# Monitor
monitor_engine.scheduler / monitor_engine.publisher

# Orchestrator
llm_orchestrator (Provider, Timeout, schema validate)
```

### 11.3 Kommandos (Beispiele)

```bash
# Readiness Edge
curl -sS "http://localhost:8000/ready" | python -m json.tool
curl -sS "http://localhost:8000/v1/system/health" -H "Authorization: Bearer <JWT>" | python -m json.tool

# Compose
docker compose logs --tail=200 api-gateway market-stream monitor-engine llm-orchestrator

# Healthcheck-Skript (lokal / edge-only laut Doku)
bash scripts/healthcheck.sh
```

### 11.4 Häufige HTTP-/Fehlercodes (Kurz)

| Code / Text               | Typische Ursache               |
| ------------------------- | ------------------------------ |
| BFF **503** + Gateway/JWT | Konfiguration Dashboard-Server |
| **502** LLM               | Orchestrator/OpenAI/Forward    |
| **503** `/v1/live/stream` | SSE aus oder Redis fehlt       |
| Gateway **503** LLM_ORCH  | Basis-URL/Key fehlt            |
| **401/403**               | Auth/Rollen                    |

---

_Ende der Übergabedatei._
