# Staging- und Production-Paritaet (kein Host-Loopback im Runtime-Netz)

Ziel: Staging soll sich wie Production verhalten — **keine** `localhost` / `127.0.0.1` / `::1` in URLs, die **andere Container** oder **Peers** erreichen müssen. Host-Loopback bezeichnet in jedem Container **den jeweiligen Container selbst**, nicht den Dienst auf dem Host.

## Validierung

| Befehl | Profil / Datei | Regel (Kurz) |
|--------|------------------|--------------|
| `pnpm config:validate:production` | `.env.production` | **Schlaegt fehl**, sobald loopback-Hosts in oben genannten Variablen oder in `HEALTH_URL_*` / `READINESS_REQUIRE_URLS` vorkommen. |
| Staging-Datei (eigenes Env) | `python tools/validate_env_profile.py --env-file .env.staging --profile staging` | Gleiche Regeln; `.env.staging` liegt meist **nicht** im Git — lokal/CI anlegen. |
| `pnpm config:validate:shadow` | `.env.shadow` | Gleiche URL-Strikte wie Staging/Production; Health-Regeln s. `bootstrap_env_checks`. |

Im Detail nutzt `tools/validate_env_profile.py` `config/bootstrap_env_checks.bootstrap_env_consistency_issues()`:

- **Profile `staging`, `shadow` und `production`:** `API_GATEWAY_URL`, `DASHBOARD_URL`, `FRONTEND_URL`, `APP_BASE_URL`, `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL` dürfen **nicht** auf `localhost` / `127.0.0.1` / `::1` zeigen. Erlaubt: Docker-Dienstnamen (z. B. `http://api-gateway:8000` fuer Server-intern) oder oeffentliche/externe Basen.
- **Profile `staging`, `shadow`, `production`:** jede `HEALTH_URL_*` muss im Container/Peer sinnvoll erreichbar sein (typisch `http://<dienstname>:<port>/ready` laut `docker-compose` oder oeffentliche Health-URL), **kein** 127.0.0.1-Loopback.
- **`READINESS_REQUIRE_URLS`**, `LLM_ORCH_BASE_URL`, `DATABASE_URL_DOCKER` / `REDIS_URL_DOCKER`:** unveraendert strikt, siehe `config/bootstrap_env_checks.py` und `config/bootstrap_env_truth.py`.
- Fuer `API_GATEWAY_URL` in **Container-Staging/Production** ist ein Host wie `api-gateway` **zulaessig**; die aeltere Regel *„kein Docker-Dienstname in Host-Context“* gilt in diesen Profilen **nicht** (sie wuerde ehrliche Deploy-ENV faelschlich verwerfen).

## Dashboard (Next.js) Server-Env

- Unter `NODE_ENV=production` verwendet `apps/dashboard/src/lib/server-env.ts` **keinen** Fallback auf `http://127.0.0.1:8000`. Ist `API_GATEWAY_URL` auf einen Loopback-Host gesetzt, liefert die BFF-URL (default) leer, bis eine gueltige Basis konfiguriert ist.
- Nur zur **Not**-Eskalation: `ALLOW_API_GATEWAY_LOOPBACK_IN_PRODUCTION=true` (Test/Debug; nicht fuer echtes Production empfohlen).

## Lokal vs. Runtime

- **Lokal (Host)**: `API_GATEWAY_URL=http://127.0.0.1:8000` bleibt fuer Profil `local` erlaubt in der bisherigen Matrix.
- **CI / Quality Gate:** `pnpm config:validate:production` muss gruen sein, bevor Production-Deploy; bei rotem Lauf: alle gemeldeten Zeilen in `.env.production` bereinigen.

## Siehe auch

- `config/bootstrap_env_truth.py` – `DOCKER_COMPOSE_SERVICE_HOSTS`
- `docs/env_profiles.md`, `docs/CONFIGURATION.md`
