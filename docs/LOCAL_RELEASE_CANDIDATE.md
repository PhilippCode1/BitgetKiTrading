# Lokaler Release Candidate (Compose)

Ziel: Reproduzierbarer Start mit `docker-compose.yml` und `.env.local` im **Repo-Root**, ohne versteckte Handgriffe. Zusätzliche Engine-Ports auf dem Host sind **nicht** nötig (Edge-only).

API-Vertraege, Beispiel-JSON Kernendpunkte, Zahlungen sandbox/live: **`docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md`**.

## Voraussetzungen

- Docker Desktop (Windows) bzw. Docker Engine + Compose v2
- `.env.local` aus `.env.local.example` erzeugen und mindestens **`POSTGRES_PASSWORD`** setzen; `DATABASE_URL` / `DATABASE_URL_DOCKER` und `REDIS_URL` / `REDIS_URL_DOCKER` müssen zum gleichen Passwort bzw. zu `redis:6379` passen (siehe Beispieldatei)
- Lokal typisch: **`GATEWAY_ENFORCE_SENSITIVE_AUTH=false`** und **`PRODUCTION=false`**, damit sensible API-Pfade ohne JWT erreichbar sind (siehe `.env.local.example`)

## Standard-Ports (Edge, Loopback)

| Dienst              | Host (Default)                       | Port |
| ------------------- | ------------------------------------ | ---- |
| API-Gateway         | `COMPOSE_EDGE_BIND` oder `127.0.0.1` | 8000 |
| Dashboard           | gleicher Bind                        | 3000 |
| Grafana (Profil)    | gleicher Bind                        | 3001 |
| Prometheus (Profil) | gleicher Bind                        | 9090 |

Interne Engines (8010–8120) sind nur im Docker-Netz `bitget_ai_net` erreichbar, nicht auf dem Host — siehe `docs/compose_runtime.md`.

## Start (komplett)

**Windows (empfohlen, inkl. Warten auf Container-Health):**

```powershell
cd <REPO-ROOT>
pnpm run dev:up
```

Oder explizit mit Env-Datei:

```powershell
docker compose --env-file .env.local -f docker-compose.yml up -d --build
```

**Linux/macOS/Git Bash (inkl. Retry auf HTTP-Health):**

```bash
cd <REPO-ROOT>
bash scripts/rc_local_stack.sh
```

## Stop

```powershell
docker compose --env-file .env.local -f docker-compose.yml down
```

```powershell
pnpm run dev:down
```

## DB-Reset (leere Datenbank, Volumes weg)

```powershell
pnpm run dev:reset-db
```

Oder:

```powershell
docker compose --env-file .env.local -f docker-compose.yml down -v
```

Anschließend erneut **Start** — der Job `migrate` läuft wieder durch.

## Status

```powershell
docker compose --env-file .env.local -f docker-compose.yml ps
```

```powershell
pnpm run dev:status
```

## Logs pro Service

Ersetze `<service>` z. B. durch `api-gateway`, `dashboard`, `market-stream`, `postgres`, `migrate`:

```powershell
docker compose --env-file .env.local -f docker-compose.yml logs -f --tail=200 <service>
```

Alle Dienste:

```powershell
docker compose --env-file .env.local -f docker-compose.yml logs -f --tail=100
```

## Health-Checks (Pflichtablauf RC)

Nach `up -d` (Stack muss fertig sein, erstes Mal ggf. mehrere Minuten):

**1) Edge-only wie in CI (benötigt `curl` + `python`):**

```powershell
$env:HEALTHCHECK_EDGE_ONLY="true"
$env:API_GATEWAY_URL="http://127.0.0.1:8000"
$env:DASHBOARD_URL="http://127.0.0.1:3000"
bash scripts/healthcheck.sh
```

**2) Ohne Bash/curl (nur Python, Windows-freundlich):**

```powershell
pnpm run rc:health
```

bzw. `pwsh scripts/rc_health.ps1`

Prüft u. a. `/ready`, Dashboard `/api/health`, `/v1/system/health`, Paper/Learning/Monitor/Live-State sowie **`/v1/learning/drift/recent`** und **`/v1/learning/drift/online-state`**.

Optional: `RC_HEALTH_ATTEMPTS` (Default `6`) und `RC_HEALTH_BASE_SLEEP_SEC` (Default `3`) für Retries nach `compose up` (Next.js braucht oft etwas länger).

## Browser (Dashboard & Gateway)

- Dashboard: `http://127.0.0.1:3000` (bei `COMPOSE_EDGE_BIND=0.0.0.0` ggf. `http://localhost:3000`)
- Gateway OpenAPI/Docs: `http://127.0.0.1:8000/docs`
- Gateway Health: `http://127.0.0.1:8000/health`
- Aggregierte System-Gesundheit: `http://127.0.0.1:8000/v1/system/health`

`pnpm run dev:up` öffnet die Tabs automatisch (ohne `-NoOpen`).

## Viele offene Monitor-Alerts (ops.alerts)

- Health zeigt `monitor_alerts_open` — das ist **kein Gateway-Bug**, sondern echte Zeilen in `ops.alerts` mit `state=open`.
- **Hinweistexte** erscheinen im Dashboard auch ohne neues Gateway-Image (Fallback aus `warnings` + Zaehler).
- **Bitget-Probe** ohne API: in `.env.local` `LIVE_REQUIRE_EXCHANGE_HEALTH=false` (Default im Code ist jetzt `false`; Production setzt explizit `true`).
- Nach Pruefung lokal Alerts schliessen: SQL-Vorlage `scripts/sql/close_open_monitor_alerts_local.sql` (nur gezielt ausfuehren).

## Typische Fehler

| Symptom                                   | Ursache / Maßnahme                                                                                             |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `migrate` Exit ≠ 0                        | Postgres-Passwort/DSN stimmen nicht; `.env.local` mit `POSTGRES_PASSWORD` und `DATABASE_URL_DOCKER` abgleichen |
| Gateway `/ready` mit `postgres:false`     | `DATABASE_URL` im Gateway-Container leer/falsch                                                                |
| `redis` in `/v1/system/health` nicht `ok` | `REDIS_URL` im Container; Redis-Container und `depends_on` prüfen                                              |
| `services` mit `error` / `degraded`       | Ziel-Engine-Logs; Cold-Start: mehrere Minuten warten, `rc_health` / `healthcheck.sh` erneut                    |
| Dashboard 502/503                         | Gateway nicht healthy; `docker compose ps`, `api-gateway`-Logs                                                 |
| `401` auf API-Pfaden                      | `GATEWAY_ENFORCE_SENSITIVE_AUTH=false` (lokal) oder JWT / `X-Gateway-Internal-Key`                             |
| Healthcheck.sh `mktemp` unter Windows     | Git Bash nutzen oder `pnpm run rc:health` (Python)                                                             |

## Pflicht-Prüfung (Release Candidate)

```powershell
docker compose --env-file .env.local -f docker-compose.yml down
# optional: DB-Reset
# docker compose --env-file .env.local -f docker-compose.yml down -v
docker compose --env-file .env.local -f docker-compose.yml up -d --build
docker compose --env-file .env.local -f docker-compose.yml ps
pnpm run rc:health
```

**Evidenz-Ordner (fuer Reviews):** `pnpm run rc:evidence` schreibt nach `artifacts/release-evidence/<timestamp>/`.

Erwartung: `rc_health_edge` meldet grün; `warnings` in `/v1/system/health` (z. B. stale Daten) sind **erlaubt** und werden ausgegeben, solange alle Service-Subchecks `ok` sind.

## Skripte (keine versteckten Sondergriffe)

| Skript                                                | Zweck                                                    |
| ----------------------------------------------------- | -------------------------------------------------------- |
| `scripts/dev_up.ps1`                                  | `up -d`, Warten auf Health, Ports, Browser               |
| `scripts/dev_down.ps1`                                | `down`                                                   |
| `scripts/dev_reset_db.ps1`                            | `down -v`                                                |
| `scripts/rc_health.ps1` / `scripts/rc_health_edge.py` | HTTP-RC-Checks an Edge                                   |
| `scripts/rc_local_stack.sh`                           | `down` → `up -d --build` → Retry `rc_health_edge` (Unix) |
| `scripts/healthcheck.sh`                              | Voll- oder Edge-only (mit `HEALTHCHECK_EDGE_ONLY=true`)  |
