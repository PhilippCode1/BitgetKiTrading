# bitget-btc-ai — Systemtopologie und Dienste (ChatGPT-Übergabe)

**Dokumenttyp:** Laufzeit-Topologie, Ports, Health, Abhängigkeiten, Betriebskritikalität.  
**Stand:** 2026-04-04.  
**Evidenz:** **verifiziert** = aus `docker-compose.yml`, `docker-compose.local-publish.yml`, `scripts/bootstrap_stack.sh`, `docs/compose_runtime.md`, `docs/stack_readiness.md`, `services/api-gateway/src/api_gateway/app.py`, `config/gateway_settings.py` ableitbar und/oder durch lokales Kommando bestätigt. **abgeleitet** = aus Doku/Logik ohne separates Laufzeit-Experiment. **nicht verifiziert (Laufzeit)** = in dieser Umgebung kein erreichbarer Stack getestet.

---

## 1. Management-Zusammenfassung

| Aspekt                              | Inhalt                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Netz**                            | Ein Docker-Bridge-Netz `bitget_ai_net`; Dienste sprechen per **DNS-Namen** (`market-stream`, `api-gateway`, …). **verifiziert:** `docker-compose.yml`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Edge (Basis-Compose)**            | Nur **API-Gateway :8000** und **Dashboard :3000** auf dem Host gemappt; Bind-Standard **`127.0.0.1`** (`COMPOSE_EDGE_BIND`). **verifiziert:** `docker-compose.yml`, Kommentar Kopf.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **Lokal + Host-Ports aller Worker** | Zusätzlich `docker-compose.local-publish.yml` veröffentlicht Postgres, Redis und HTTP-Ports der Engines auf den Host. **verifiziert:** `docker-compose.local-publish.yml`, `scripts/bootstrap_stack.sh` (Profil `local`).                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Shadow / Production auf Host**    | Empfohlen **ohne** `local-publish`-Overlay — interne Ports nicht auf dem Host. Smoke mit `HEALTHCHECK_EDGE_ONLY=true`. **verifiziert:** `docs/compose_runtime.md`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **Startlogik**                      | `depends_on` mit `condition: service_healthy` / `service_completed_successfully` erzwingt eine **kompatible** Reihenfolge; parallel startbare Dienste (z. B. nach gemeinsamen Voraussetzungen) werden von Compose parallelisiert. **verifiziert:** `docker-compose.yml`.                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Gateway-Readiness**               | `GET /ready` prüft Postgres, Redis, Schema-Check und optional **Peer-URLs** aus `READINESS_REQUIRE_URLS` (`append_peer_readiness_checks`). **verifiziert:** `services/api-gateway/src/api_gateway/app.py`, `config/settings.py` (`readiness_require_urls_raw`). Im **Basis-Compose** ist `READINESS_REQUIRE_URLS` für `api-gateway` **nicht** gesetzt — die Peers werden primär über **Compose-`depends_on`** vor dem Gateway-Start healthy gehalten; laufzeitfähige Nachprüfung aller Worker über Gateway `/ready` setzt ggf. **zusätzliche ENV** voraus. **verifiziert:** Abgleich `docker-compose.yml` (kein `READINESS_REQUIRE_URLS` am Service `api-gateway`) + Code. |
| **Aggregierte Ops-Sicht**           | `GET /v1/system/health` (Gateway) — laut Doku für Gesamtstatus; Details `docs/stack_readiness.md`. **abgeleitet:** Doku; **nicht verifiziert (Laufzeit):** kein Live-Call in der Erstellungsumgebung.                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **Kritischster Pfad**               | `postgres` → `migrate` → Daten-Pipeline ab `market-stream` → `news-engine` (braucht `llm-orchestrator`) → `signal-engine` → `paper-broker` / `live-broker` → `alert-engine` / `learning-engine` → **`api-gateway`** → **`dashboard`**. `monitor-engine` hängt am Gateway, blockiert das Gateway **nicht**. **verifiziert:** `docker-compose.yml` `depends_on`.                                                                                                                                                                                                                                                                                                             |

---

## 2. Vollständige Diensteliste

**Basis-Stack (ohne Observability-Profil)** — **verifiziert:** `docker compose -f docker-compose.yml config --services` (2026-04-04, Windows; siehe Anhang A).

| #   | Compose-Service                             |
| --- | ------------------------------------------- |
| 1   | `postgres`                                  |
| 2   | `redis`                                     |
| 3   | `migrate` (einmaliger Job, `restart: "no"`) |
| 4   | `market-stream`                             |
| 5   | `feature-engine`                            |
| 6   | `structure-engine`                          |
| 7   | `drawing-engine`                            |
| 8   | `llm-orchestrator`                          |
| 9   | `news-engine`                               |
| 10  | `signal-engine`                             |
| 11  | `paper-broker`                              |
| 12  | `live-broker`                               |
| 13  | `alert-engine`                              |
| 14  | `learning-engine`                           |
| 15  | `api-gateway`                               |
| 16  | `monitor-engine`                            |
| 17  | `dashboard`                                 |

**Zusätzlich (Profil `observability`):** `prometheus`, `grafana`. **verifiziert:** `docker-compose.yml` (`profiles: observability`).

---

## 3. Tabelle: Dienstname, Rolle, Port, Health-URL, harte Abhängigkeiten

**Legende Ports:** „HTTP intern“ = Port im Container; „Host Basis“ = nur `docker-compose.yml`. „Host + Overlay“ = zusätzlich `docker-compose.local-publish.yml` (`COMPOSE_LOCAL_PUBLISH_BIND`, Standard `127.0.0.1`).

| Dienst             | Rolle                         | HTTP-Port (intern)                           | Health / Readiness (primär)                                        | Harte Compose-`depends_on` (Kern)                                                                                             |
| ------------------ | ----------------------------- | -------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `postgres`         | PostgreSQL 16                 | 5432 TCP                                     | **Docker-Healthcheck:** `pg_isready` (kein HTTP)                   | —                                                                                                                             |
| `redis`            | Redis 7                       | 6379 TCP                                     | **Docker-Healthcheck:** `redis-cli ping`                           | —                                                                                                                             |
| `migrate`          | Schema-Migrationen            | —                                            | **Exit 0** (kein HTTP)                                             | `postgres` healthy                                                                                                            |
| `market-stream`    | Bitget-Feed, REST/WS          | **8010**                                     | `http://127.0.0.1:8010/ready` (Compose-Healthcheck)                | `migrate` completed, `postgres`, `redis` healthy                                                                              |
| `feature-engine`   | Features                      | **8020**                                     | `…:8020/ready`                                                     | `migrate`, `postgres`, `redis`, `market-stream` healthy                                                                       |
| `structure-engine` | Struktur                      | **8030**                                     | `…:8030/ready`                                                     | `migrate`, `postgres`, `redis`, `market-stream` healthy                                                                       |
| `drawing-engine`   | Drawings                      | **8040**                                     | `…:8040/ready`                                                     | `migrate`, `postgres`, `redis`, `structure-engine` healthy                                                                    |
| `llm-orchestrator` | LLM-API (intern)              | **8070**                                     | `…:8070/ready`                                                     | `redis` healthy                                                                                                               |
| `news-engine`      | News-Ingest/Score             | **8060**                                     | `…:8060/ready`                                                     | `migrate`, `postgres`, `redis`, `llm-orchestrator` healthy                                                                    |
| `signal-engine`    | Deterministischer Signal-Kern | **8050**                                     | `…:8050/ready`                                                     | `migrate`, `postgres`, `redis`, `feature-engine`, `structure-engine`, `drawing-engine`, `news-engine` healthy                 |
| `paper-broker`     | Paper-Ausführung              | **8085**                                     | `…:8085/ready`                                                     | `migrate`, `postgres`, `redis`, `market-stream`, `structure-engine`, `drawing-engine`, `signal-engine`, `news-engine` healthy |
| `live-broker`      | Live/Control-Plane            | **8120**                                     | `…:8120/ready`                                                     | `migrate`, `postgres`, `redis`, `signal-engine`, `paper-broker` healthy                                                       |
| `learning-engine`  | Registry/Backtests/Drift      | **8090**                                     | `…:8090/ready`                                                     | `migrate`, `postgres`, `redis`, `paper-broker`, `signal-engine`, `news-engine`, `structure-engine`, `drawing-engine` healthy  |
| `alert-engine`     | Alerts/Telegram/Outbox        | **8100**                                     | `…:8100/ready`                                                     | `migrate`, `postgres`, `redis`, `signal-engine`, `news-engine`, `paper-broker` healthy                                        |
| `api-gateway`      | HTTP-Edge, Proxies            | **8000**                                     | `GET /ready` (JSON `ready: true` erzwungen im Compose-Healthcheck) | `migrate`, `postgres`, `redis`, alle genannten Worker inkl. `learning-engine`, `alert-engine`, `live-broker` healthy          |
| `monitor-engine`   | Metriken/Alerts über Streams  | **8110**                                     | `…:8110/ready`                                                     | u. a. `api-gateway` healthy + dieselbe Worker-Kette wie Gateway                                                               |
| `dashboard`        | Next.js UI                    | **3000**                                     | `GET http://127.0.0.1:3000/api/health` (Compose-Healthcheck)       | `api-gateway` healthy                                                                                                         |
| `prometheus`       | Metrics (Profil)              | **9090** (Container; Host-Map siehe Compose) | Image-Standard / kein Repo-Healthcheck wie Python-Services         | `api-gateway` + Worker-Kette (siehe Compose)                                                                                  |
| `grafana`          | Dashboards (Profil)           | **3000** intern → Host **3001**              | Grafana-UI                                                         | `prometheus` started                                                                                                          |

**Peer-Readiness pro Worker (ENV):** Viele Dienste setzen `READINESS_REQUIRE_URLS` auf Upstream-`/ready` (kommagetrennt). **verifiziert:** `docker-compose.yml` je Service.

---

## 4. Startreihenfolge des Systems

### 4.1 Von Docker erzwungene Phasen (vereinfacht)

| Phase | Dienste / Ereignis                   | Bemerkung                                                                       |
| ----- | ------------------------------------ | ------------------------------------------------------------------------------- |
| A     | `postgres`, `redis`                  | parallel, bis `healthy`                                                         |
| B     | `migrate`                            | nach A; bei Erfolg `completed_successfully`                                     |
| C     | `llm-orchestrator`                   | parallel zu B möglich, sobald `redis` healthy (kein `migrate`-Zwang im Compose) |
| D     | `market-stream`                      | nach B + A                                                                      |
| E     | `feature-engine`, `structure-engine` | nach D                                                                          |
| F     | `drawing-engine`                     | nach `structure-engine`                                                         |
| G     | `news-engine`                        | nach B + A + C                                                                  |
| H     | `signal-engine`                      | nach E + F + G                                                                  |
| I     | `paper-broker`                       | nach D + F + H + G                                                              |
| J     | `live-broker`                        | nach H + I                                                                      |
| K     | `learning-engine`                    | nach I + H + G + F                                                              |
| L     | `alert-engine`                       | nach H + G + I                                                                  |
| M     | `api-gateway`                        | nach I, J, K, L + Pipeline-Worker                                               |
| N     | `monitor-engine`                     | nach M + Worker-Kette                                                           |
| O     | `dashboard`                          | nach M                                                                          |

**verifiziert:** ausschließlich aus `docker-compose.yml` `depends_on` abgeleitet.

### 4.2 Operative Beschreibung (Doku)

Die Tabelle in `docs/stack_readiness.md` (Stufen 0–10) bildet dieselbe Kette **inhaltlich** ab, weicht in der **Nummerierung/Gruppierung** leicht von der strikten Compose-Parallelität ab. **verifiziert:** Datei `docs/stack_readiness.md`; **abgeleitet:** „exakt gleiche“ Reihenfolge wie Compose-Zeile für Zeile.

### 4.3 Bootstrap-Skript

`bash scripts/bootstrap_stack.sh <local|shadow|production>` wählt Compose-Files: **local** = `docker-compose.yml` + `docker-compose.local-publish.yml`; **shadow|production** = nur `docker-compose.yml`. **verifiziert:** `scripts/bootstrap_stack.sh` Zeilen 104–112.

---

## 5. Was passiert, wenn ein Dienst ausfällt

| Ausfall                             | Kurzwirkung                                                                                                                                                              | Bemerkung / Evidenz                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| **postgres** / **redis**            | Stack bricht zusammen; Worker werden `unhealthy`, Gateway-`/ready` scheitert an DB/Redis-Checks.                                                                         | **verifiziert:** praktisch alle Services hängen an DB/Redis; Gateway `app.py` `/ready`.  |
| **migrate** (fehlgeschlagen)        | Nachfolger starten nicht (Condition `service_completed_successfully`).                                                                                                   | **verifiziert:** `docker-compose.yml`.                                                   |
| **market-stream**                   | `feature-engine`, `structure-engine` werden nicht healthy; Kaskade bis `signal-engine`.                                                                                  | **verifiziert:** `depends_on` + `READINESS_REQUIRE_URLS` bei Feature/Structure.          |
| **llm-orchestrator**                | `news-engine` nicht healthy → `signal-engine` blockiert → Broker-Kette blockiert.                                                                                        | **verifiziert:** `news-engine` `depends_on` + `READINESS_REQUIRE_URLS`.                  |
| **signal-engine**                   | `paper-broker`, `live-broker`, `alert-engine`, indirekt Gateway blockiert.                                                                                               | **verifiziert:** `depends_on`.                                                           |
| **paper-broker**                    | `live-broker`, `learning-engine`, `alert-engine` betroffen; Gateway wartet auf diese.                                                                                    | **verifiziert:** `depends_on`.                                                           |
| **api-gateway**                     | Dashboard-Healthcheck fehlschlägt; kein HTTP-Edge; UI/API von außen weg.                                                                                                 | **verifiziert:** `dashboard` `depends_on: api-gateway`.                                  |
| **monitor-engine**                  | **Kein** Blocker für `api-gateway` oder `dashboard` im Compose. Monitoring/Alerting aus Monitor-Pfad weg oder veraltet, bis Neustart.                                    | **verifiziert:** `api-gateway` listet `monitor-engine` nicht unter `depends_on`.         |
| **Laufzeit-Ausfall nach „healthy“** | Compose startet ggf. **Restart** (`unless-stopped`); zwischenzeitlich können Routes 502/503 liefern, `/ready` kann `false` werden, abhängig von Service und Gateway-ENV. | **abgeleitet:** typisches Docker-Verhalten; **nicht verifiziert (Laufzeit):** Lasttests. |

---

## 6. Welche Dienste nur intern erreichbar sein sollen

| Kontext                           | Intern (kein Host-Port im Basis-Compose)                                                                                                                                                                                                       | Bemerkung                                                                                                                                                     |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Shadow/Production (empfohlen)** | `postgres`, `redis`, alle Python-Worker (`8010`–`8120`), `monitor-engine`                                                                                                                                                                      | Nur `api-gateway:8000`, `dashboard:3000` nach außen. **verifiziert:** `docs/compose_runtime.md`, `docker-compose.yml` (keine `ports` bei Workern außer Edge). |
| **Local + Overlay**               | Sicherheitsmodell schwächer: alle genannten Ports auch auf `127.0.0.1` (oder `COMPOSE_LOCAL_PUBLISH_BIND`)                                                                                                                                     | Nur für Dev/Debug. **verifiziert:** `docker-compose.local-publish.yml`.                                                                                       |
| **LLM-Orchestrator**              | Sollte **nicht** öffentlich ohne Auth erreichbar sein; Zugriff über Gateway mit `INTERNAL_API_KEY` / interne Netze. **abgeleitet:** `API_INTEGRATION_STATUS.md`, `services/llm-orchestrator` Internal-Auth — **nicht verifiziert (Pen-Test).** |

---

## 7. Welche Dienste nach außen freigegeben sind

| Endpoint               | Host (Basis-Compose)                                | Konfiguration                         |
| ---------------------- | --------------------------------------------------- | ------------------------------------- |
| API-Gateway            | `${COMPOSE_EDGE_BIND:-127.0.0.1}:8000:8000`         | **verifiziert:** `docker-compose.yml` |
| Dashboard              | `${COMPOSE_EDGE_BIND:-127.0.0.1}:3000:3000`         | **verifiziert:** `docker-compose.yml` |
| Prometheus             | `:9090` nur mit Profil `observability`              | **verifiziert:** `docker-compose.yml` |
| Grafana                | `:3001:3000` nur mit Profil `observability`         | **verifiziert:** `docker-compose.yml` |
| Alle Worker-HTTP-Ports | Host nur mit **`docker-compose.local-publish.yml`** | **verifiziert:** Overlay-Datei        |

**TLS/Reverse-Proxy:** außerhalb Compose; Vorlagen `infra/reverse-proxy/`. **verifiziert:** `docs/compose_runtime.md`.

---

## 8. Wo im Repo die jeweilige Konfiguration liegt

| Thema                                   | Pfade                                                                                          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Compose-Topologie, Healthchecks, Ports  | `docker-compose.yml`, `docker-compose.local-publish.yml`                                       |
| Runtime-Doku (Profile, Edge-only Smoke) | `docs/compose_runtime.md`, `docs/stack_readiness.md`                                           |
| Bootstrap, Compose-File-Wahl pro Profil | `scripts/bootstrap_stack.sh`, `scripts/bootstrap_stack.ps1`, `scripts/dev_up.ps1`              |
| Service-Inventar (YAML)                 | `infra/service-manifest.yaml`                                                                  |
| Gateway: CORS, Edge-ENV, `HEALTH_URL_*` | `docker-compose.yml` (`api-gateway.environment`), `config/gateway_settings.py`                 |
| Gateway: `/health`, `/ready`            | `services/api-gateway/src/api_gateway/app.py`                                                  |
| Host-Smoke, `HEALTHCHECK_EDGE_ONLY`     | `scripts/healthcheck.sh`                                                                       |
| ENV-Profile                             | `docs/env_profiles.md`, `.env.local.example`, `.env.shadow.example`, `.env.production.example` |
| Monitor: Service-URL-Liste              | `docker-compose.yml` → `MONITOR_SERVICE_URLS` bei `monitor-engine`                             |

---

## 9. Live-Nachweise oder Startversuche mit Ergebnis

| Prüfung                                                       | Ergebnis                                                                                                                                                                                            | Datum / Umgebung                          |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `docker compose -f docker-compose.yml config --services`      | **Exit 0**; Serviceliste wie Abschnitt 2 (ohne Observability-Profil). Zusätzlich **Warnungen**, u. a. fehlendes `POSTGRES_PASSWORD`, `APP_BASE_URL`, … — **keine** geladene `.env` in dieser Shell. | 2026-04-04, Windows PowerShell, Repo-Root |
| `Invoke-WebRequest http://127.0.0.1:8000/health` (Timeout 2s) | **Zeitüberschreitung** — auf dieser Maschine kein antwortender Gateway-Prozess unter Loopback.                                                                                                      | 2026-04-04                                |
| Vollständiger `docker compose up` + End-to-End-Health         | **nicht verifiziert (Laufzeit)** — nicht ausgeführt (Secrets/Build-Zeit).                                                                                                                           | —                                         |

---

## 10. Typische Fehlerbilder im laufenden Stack

| Symptom                                                                | Häufige Ursache                                                                                          | Beleg                                                                              |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Gateway `/ready` zeigt Worker „down“, Daten leer                       | `HEALTH_URL_*` zeigen im Container auf `localhost` statt `http://<service>:<port>/ready`                 | `API_INTEGRATION_STATUS.md` Rang 1                                                 |
| Dashboard BFF **503**                                                  | `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt/falsch/alter Prozess                                             | `API_INTEGRATION_STATUS.md` Rang 2                                                 |
| Healthcheck-Skript schlägt fehl auf Shadow/Prod ohne Engine-Host-Ports | Default-URLs in `healthcheck.sh` erwarten `localhost:8010` … — mit reinem Basis-Compose nicht erreichbar | `scripts/healthcheck.sh`, `docs/compose_runtime.md` (`HEALTHCHECK_EDGE_ONLY=true`) |
| `news-engine` startet nicht                                            | `llm-orchestrator` nicht ready oder Redis down                                                           | `docker-compose.yml` `depends_on`                                                  |
| Gateway startet nicht                                                  | Ein beliebiger Worker in der `depends_on`-Kette bleibt `unhealthy`                                       | `docker-compose.yml` `api-gateway.depends_on`                                      |
| BITGET_USE_DOCKER_DATASTORE_DSN=true + Loopback-HEALTH-URLs            | Validierungsfehler beim Gateway-Start                                                                    | `config/gateway_settings.py` (`use_docker_datastore_dsn`-Validator)                |

---

## 11. Übergabe an ChatGPT

1. **Quelle der Topologie:** immer zuerst `docker-compose.yml` + Profil/Overlay laut `docs/compose_runtime.md`.
2. **Zwei Betriebsbilder unterscheiden:** (a) Basis-Compose = nur Edge-Ports; (b) local-publish = alle Worker-Ports auf dem Host für Debugging.
3. **Gateway `/ready` vs. Compose:** Compose stellt sicher, dass beim **ersten** Start die Kette healthy ist; ob `/ready` dauerhaft alle Peers spiegelt, hängt von `READINESS_REQUIRE_URLS` am Gateway ab — im Repo-Compose **nicht** gesetzt.
4. **monitor-engine** ist für den Start von Gateway/Dashboard **nicht** blockierend — aber für Betriebsüberwachung relevant (`MONITOR_SERVICE_URLS`).
5. **Smoke:** `docs/stack_readiness.md` und `scripts/healthcheck.sh`; Shadow/Prod Edge-only laut `docs/compose_runtime.md`.

---

## 12. Anhang mit Kommandos und Outputs

### Anhang A — `docker compose -f docker-compose.yml config --services`

**Kommando:** `docker compose -f docker-compose.yml config --services`  
**Arbeitsverzeichnis:** Repository-Root `bitget-btc-ai`.

**Stdout (Auszug, Reihenfolge wie vom Befehl geliefert):**

```
redis
postgres
migrate
market-stream
structure-engine
drawing-engine
feature-engine
llm-orchestrator
news-engine
signal-engine
paper-broker
live-broker
alert-engine
learning-engine
api-gateway
dashboard
monitor-engine
```

**Hinweis:** Die Reihenfolge ist **keine** garantierte Boot-Reihenfolge (alphabetisch/intern sortiert). Die tatsächliche Abfolge folgt `depends_on` (Abschnitt 4).

**Stderr:** zahlreiche Compose-Warnungen wegen **nicht gesetzter** Variablen (`POSTGRES_PASSWORD`, `NEXT_PUBLIC_*`, `APP_BASE_URL`, …), weil beim Befehl **keine** `.env`-Datei geladen wurde. **verifiziert:** Konsolenoutput 2026-04-04.

### Anhang B — Referenzkommandos (nicht alle ausgeführt)

| Zweck                          | Kommando                                                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Stack mit lokalem Host-Publish | `docker compose -f docker-compose.yml -f docker-compose.local-publish.yml up -d --build` + `COMPOSE_ENV_FILE=.env.local` |
| Nur Basis (Shadow/Prod-Stil)   | `docker compose -f docker-compose.yml up -d --build` + passende `COMPOSE_ENV_FILE`                                       |
| Edge-only Health               | `HEALTHCHECK_EDGE_ONLY=true bash scripts/healthcheck.sh` (bash erforderlich)                                             |
| Gateway-Ready (lokal)          | `curl -sS "http://127.0.0.1:8000/ready"`                                                                                 |
| Aggregiert                     | `curl -sS "http://127.0.0.1:8000/v1/system/health"`                                                                      |

---

_Ende der Übergabedatei._
