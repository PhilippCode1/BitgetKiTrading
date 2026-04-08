# Stack-Readiness, Liveness und Startreihenfolge

## Wann ist der Stack „wirklich bereit“?

1. **Docker:** Alle relevanten Container im Zustand `healthy` (oder ohne Healthcheck `running`), siehe `docker compose ps`.
2. **Readiness (`GET …/ready`):** JSON mit `"ready": true` und alle Eintraege unter `checks` mit `ok: true` (keine stillen Teildefekte).
3. **Edge-Aggregat:** `GET {API_GATEWAY_URL}/v1/system/health` mit `database=ok`, `redis=ok`, und fuer jeden konfigurierten Kernservice `status: ok` (HTTP-Probe der jeweiligen Ready-URL).
4. **Dashboard:** `GET {DASHBOARD_URL}/api/health` mit `status: ok`.
5. **Optional:** Keine blockierenden `warnings` im System-Health (z. B. Stale-Daten, offene Monitor-Alerts, fehlgeschlagene Alert-Outbox) — operativ bewerten, nicht automatisch als „nicht bereit“ fuer den reinen Prozessstart.

`scripts/healthcheck.sh` setzt (1)+(2)+(3)+(4) fuer local mit Host-URLs bzw. im Modus `HEALTHCHECK_EDGE_ONLY=true` nur Gateway + Dashboard + Aggregat um.

## Startreihenfolge (`scripts/bootstrap_stack.sh`)

| Stufe | Dienste                                             | Begruendung                         |
| ----- | --------------------------------------------------- | ----------------------------------- |
| 0     | `postgres`, `redis`                                 | Dateninfra                          |
| —     | Migrationen (`infra/migrate.py`)                    | Schema vor Workern                  |
| 1     | `market-stream`, `llm-orchestrator`                 | Kernfeeds / LLM fuer News-Pfad      |
| 2     | `feature-engine`, `structure-engine`, `news-engine` | Abgeleitete Analyse                 |
| 3     | `drawing-engine`, `signal-engine`                   | Signalpfad                          |
| 4     | `paper-broker`, `live-broker`                       | Broker / Execution-Slot             |
| 5     | `learning-engine`                                   | Lernpfad nach Paper/Signal          |
| 6     | `alert-engine`                                      | Vor Gateway (Compose-Abhaengigkeit) |
| 7     | `api-gateway`                                       | Edge nach allen Upstreams           |
| 8     | `monitor-engine`                                    | Braucht erreichbares Gateway        |
| 9     | `prometheus`, `grafana`                             | Nur mit `--with-observability`      |
| 10    | `dashboard`                                         | UI zuletzt                          |

Wartezeiten: `wait_for_service` nutzt lineares Anwachsen der Poll-Pause bis `BOOTSTRAP_POLL_MAX_SEC` (Standard 10s). Bei Fehler: `docker compose logs --tail 120` fuer den betroffenen Service.

## Kernservices: Liveness vs. Readiness

| Service          | Liveness (Prozess)          | Readiness (hart)                                                                             | Tolerierte Degradierung               | Compose `restart` |
| ---------------- | --------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------- |
| postgres / redis | TCP / `pg_isready` / `PING` | healthy                                                                                      | —                                     | `unless-stopped`  |
| market-stream    | HTTP-Server                 | DB, Redis, Eventbus verbunden, WS `connected`, Candle-Initial-Load, Orderbook nicht desync   | `/health` kann Detailzustaende zeigen | `unless-stopped`  |
| feature … signal | HTTP                        | DB + Redis + `READINESS_REQUIRE_URLS` (Peer-`/ready`)                                        | —                                     | `unless-stopped`  |
| news-engine      | HTTP                        | DB + Redis + LLM-Orchestrator ready                                                          | —                                     | `unless-stopped`  |
| llm-orchestrator | HTTP                        | Redis                                                                                        | Kein DB-Zwang                         | `unless-stopped`  |
| paper-broker     | HTTP                        | DB, Redis, **Eventbus-Ping**, Peer-Ready (Signal+News)                                       | `/health` bei teilweise degradiert    | `unless-stopped`  |
| learning-engine  | HTTP                        | DB + Redis + Paper-Broker ready                                                              | —                                     | `unless-stopped`  |
| live-broker      | HTTP                        | DB, Redis, Eventbus, Schema, ggf. Bitget-Probes/Serverzeit laut Settings                     | `/health` `degraded` bei Reconcile    | `unless-stopped`  |
| alert-engine     | HTTP                        | DB, Redis, Outbox ohne `failed`-Messages, Peer-Ready                                         | `/health` zeigt Outbox-Zaehler        | `unless-stopped`  |
| api-gateway      | HTTP                        | DB + Redis (keine zirkulaeren Peer-URLs)                                                     | —                                     | `unless-stopped`  |
| monitor-engine   | HTTP                        | DB, Redis, Eventbus, Scheduler (Boot-Grace `MONITOR_READINESS_BOOT_GRACE_MS`), Gateway ready | `/health` bei stale Scheduler         | `unless-stopped`  |
| dashboard        | Node                        | `api/health`                                                                                 | —                                     | `unless-stopped`  |

Peer-Ketten werden ueber **`READINESS_REQUIRE_URLS`** (kommagetrennt) und parallele HTTP-GETs mit festem Timeout gesetzt — **ohne Zufall** im Trading-Kern.

## Umgebungsvariablen (Auszug)

| Variable                                                          | Bedeutung                                          |
| ----------------------------------------------------------------- | -------------------------------------------------- |
| `READINESS_REQUIRE_URLS`                                          | Kommagetrennte `/ready`-URLs von Upstream-Services |
| `READINESS_PEER_TIMEOUT_SEC`                                      | Timeout pro Peer (Standard 2.5)                    |
| `MONITOR_READINESS_BOOT_GRACE_MS`                                 | Monitor: erster Scheduler-Tick optional verzoegert |
| `WAIT_TIMEOUT_SEC`                                                | Bootstrap: max. Wartezeit pro Service              |
| `BOOTSTRAP_POLL_MAX_SEC`                                          | Obere Kappe der Poll-Pause                         |
| `HEALTHCHECK_RETRY_ATTEMPTS` / `HEALTHCHECK_RETRY_BASE_SLEEP_SEC` | Lineare Wiederholungen in `healthcheck.sh`         |

## Smoke fuer Operatoren

```bash
# Nach Stack-Start (localhost mit veroeffentlichten Ports)
curl -sS "http://localhost:8000/ready" | python -m json.tool
curl -sS "http://localhost:8000/v1/system/health" | python -m json.tool
bash scripts/healthcheck.sh
```

Edge-only (ohne Engine-Ports auf dem Host):

```bash
export HEALTHCHECK_EDGE_ONLY=true API_GATEWAY_URL=http://<host>:8000 DASHBOARD_URL=http://<host>:3000
bash scripts/healthcheck.sh
```

Nach TLS / Reverse-Proxy: `curl -sS "${API_GATEWAY_URL}/v1/deploy/edge-readiness"` (keine Secrets, Checkliste).

Warten bis Compose keine `unhealthy` Services mehr meldet: `bash scripts/wait_compose_healthy.sh`.

Siehe auch: `docs/compose_runtime.md`, `docker-compose.yml` (Healthchecks, `READINESS_REQUIRE_URLS`), `docs/operator_urls_and_secrets.md`.
