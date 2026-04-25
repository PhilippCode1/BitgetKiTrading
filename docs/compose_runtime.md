# Docker Compose: Profile und Netzwerk

## Dateien

| Datei                                 | Rolle                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docker-compose.yml`                  | **Kanonisches Grundgeruest** fuer local, shadow und production: gleiche Services, Abhaengigkeiten, Healthchecks, Volumes. **Host-Ports** nur fuer Edge: **api-gateway (8000)**, **dashboard (3000)** — Standard-Bind **`127.0.0.1`** (`COMPOSE_EDGE_BIND`). Datenstores und Pipeline sind **nur im Netz `bitget_ai_net`** erreichbar. |
| `docker-compose.local-publish.yml`    | **Overlay**: mappt Postgres, Redis und alle internen Service-Ports auf den Host — Standard-Bind **`127.0.0.1`** (`COMPOSE_LOCAL_PUBLISH_BIND`).                                                                                                                                                                                       |
| `infra/tests/docker-compose.test.yml` | Test-Stack (CI-naeher), separat.                                                                                                                                                                                                                                                                                                      |

## Welches Kommando wofuer?

### Local (`.env.local`)

```bash
export COMPOSE_ENV_FILE=.env.local
docker compose -f docker-compose.yml -f docker-compose.local-publish.yml up -d --build
bash scripts/healthcheck.sh
```

Oder: `bash scripts/bootstrap_stack.sh local` (setzt Compose-Files automatisch; am Anfang `tools/compose_start_preflight.py`).

**Windows:** `pnpm dev:up` / `pwsh scripts/dev_up.ps1` nutzen **dieselbe** Kombination wie der Bootstrap (**`docker-compose.yml` + `docker-compose.local-publish.yml`**) — Host-Publish der Worker-Ports fuer Debugging (Ueberblick: `docs/structure.md`, `docs/dev-workflow.md`). Nur Edge-Ports wie Shadow/Prod: `dev_up.ps1 -NoLocalPublish`. Daten zuruecksetzen: `pnpm dev:reset-db` / `dev_reset_db.ps1` (gleiche Compose-Files wie `dev_up`).

Release-Candidate (Start, Stop, Logs, Health, typische Fehler): **`docs/LOCAL_RELEASE_CANDIDATE.md`**.

### Shadow (`.env.shadow`) / Production (`.env.production`)

Gleiches Grundgeruest — nur `COMPOSE_ENV_FILE` bzw. `--env-file` wechseln.

**Empfohlen fuer Shadow/Production auf Hosts** (keine internen Ports auf dem Host): nur Basisdatei; Edge bleibt Gateway + Dashboard (+ optional Observability):

```bash
export COMPOSE_ENV_FILE=.env.shadow
docker compose -f docker-compose.yml up -d --build
```

```bash
export COMPOSE_ENV_FILE=.env.production
docker compose -f docker-compose.yml up -d --build
```

**Shadow/Local mit localhost-Health** (wie CI / `scripts/healthcheck.sh`): Overlay zusaetzlich:

```bash
export COMPOSE_ENV_FILE=.env.shadow
docker compose -f docker-compose.yml -f docker-compose.local-publish.yml up -d --build
```

Dann funktioniert `scripts/healthcheck.sh` mit `localhost:*` **nicht** fuer interne Engines — Health ueber **Gateway** (`API_GATEWAY_URL`, z. B. `/v1/system/health`) oder Checks aus dem internen Netz.

`bash scripts/bootstrap_stack.sh shadow|production` setzt automatisch **`HEALTHCHECK_EDGE_ONLY=true`** fuer den abschliessenden Smoke (Gateway `/ready`, Dashboard `/api/health`, aggregiertes `/v1/system/health`). Manuell: `HEALTHCHECK_EDGE_ONLY=true bash scripts/healthcheck.sh`.

Anpassbar: `COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.local-publish.yml)` vor `bootstrap_stack.sh`, wenn Shadow/Prod trotzdem mit Host-Published-Engines (Debugging) laufen soll.

### Observability

```bash
docker compose -f docker-compose.yml -f docker-compose.local-publish.yml --profile observability up -d
```

`GRAFANA_ADMIN_PASSWORD` muss gesetzt sein (kein Default im Compose).

## Produktionspfad

- Dashboard-Image: **Multi-Stage Dockerfile** — `next build` + `node apps/dashboard/server.js` (kein `next dev`).
- `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` als **Build-Args** fuer das Dashboard-Image setzen (siehe `docker-compose.yml` → `dashboard.build.args`).
- API-Gateway: zusaetzliche Edge-ENV (`APP_BASE_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`, `GATEWAY_SEND_HSTS`, …) werden in Compose an den Container durchgereicht.
- Keine Secrets in `docker-compose.yml`: nur `${VAR}`-Referenzen; Werte aus `.env.*` / Secret-Injection.

## Reverse-Proxy / TLS

- Vorlage: `infra/reverse-proxy/nginx.single-host.conf` + `infra/reverse-proxy/README.md`
- Operator-URL-Matrix: **`docs/operator_urls_and_secrets.md`**
- Deploy-Check: `GET /v1/deploy/edge-readiness` am API-Gateway

## Recovery / Warten auf Healthy

```bash
bash scripts/wait_compose_healthy.sh
```

## Querverweise

- Service-Inventar / Ports: `infra/service-manifest.yaml`
- Readiness, Startreihenfolge, Smoke: **`docs/stack_readiness.md`**
- Gap-Matrix: `docs/REPO_FREEZE_GAP_MATRIX.md`
- ENV-Profile: `docs/env_profiles.md`
