# 10 — Bootstrap- und Compose-Startvertrag

**Laufzeitgrundlage:** `docs/chatgpt_handoff/02_SYSTEM_TOPOLOGIE_UND_SERVICES.md`  
**Stand:** 2026-04-05

---

## 1. Startvertrag (Kurz)

| Profil         | ENV-Datei         | Compose-Dateien                                               | Host-Ports (Ziel)                                            | Abschluss-Smoke                                  |
| -------------- | ----------------- | ------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------ |
| **local**      | `.env.local`      | `docker-compose.yml` **+** `docker-compose.local-publish.yml` | Edge **+** Worker/DB/Redis auf Loopback (Debugging)          | `scripts/healthcheck.sh` (alle URLs / localhost) |
| **shadow**     | `.env.shadow`     | nur `docker-compose.yml`                                      | typisch nur **:8000** / **:3000** (+ optional Observability) | `HEALTHCHECK_EDGE_ONLY=true` + `healthcheck.sh`  |
| **production** | `.env.production` | nur `docker-compose.yml`                                      | wie Shadow                                                   | `HEALTHCHECK_EDGE_ONLY=true` + `healthcheck.sh`  |

**Abweichung local (bewusst):** `dev_up.ps1 -NoLocalPublish` / `compose_up.ps1 -NoLocalPublish` — nur Basis-Compose (kein `local-publish`-Overlay), analog Shadow/Prod-Portmodell.

---

## 2. env_file / CONFIG_ENV_FILE

- **Compose:** `x-env-file` → `${COMPOSE_ENV_FILE:-.env.local}` (`docker-compose.yml`).
- **Bootstrap / dev_up:** setzen `COMPOSE_ENV_FILE` auf die gewählte Datei und rufen `docker compose ... --env-file <gleiche Datei>` auf.
- **App-Container:** `CONFIG_ENV_FILE` und `BITGET_USE_DOCKER_DATASTORE_DSN` aus `x-app-runtime-env` — DSNs im Netz `postgres`/`redis`, nicht Host-Loopback.

---

## 3. Diagnose vor dem Start

**`tools/compose_start_preflight.py`**

- `docker compose … config --services` muss **Exit 0** liefern.
- Heuristik: `POSTGRES_PASSWORD` leer bei erwartetem Compose-Postgres (`DATABASE_URL_DOCKER` leer oder `@postgres:`) → **Fehler**.

Wird aufgerufen von:

- `scripts/bootstrap_stack.sh` / `bootstrap_stack.ps1` (alle Profile, nach Docker-Verfügbarkeit),
- `scripts/dev_up.ps1` / `scripts/compose_up.ps1` (local).

---

## 4. Reihenfolge und Health

- **Compose** erzwingt `depends_on` mit `condition: service_healthy` / `service_completed_successfully` (siehe 02, Abschnitt 4).
- **`bootstrap_stack`**: zusätzlich **manuell gestaffelt** (Datastores → Migration → Stufen 1–8 → Dashboard), damit klare Logs und `wait_for_service` pro Stufe.
- **`dev_up` / `compose_up`**: ein `docker compose up -d` (Compose löst Abhängigkeiten selbst) + `Wait-DevStackHealthy` über die Service-Liste in `_dev_compose.ps1`.

---

## 5. Nachweise (Kommandoausgaben)

_(Ausgeführt im Repo-Root `bitget-btc-ai`, 2026-04-05.)_

### 5.1 `docker compose config --services`

Befehl:

```text
docker compose -f docker-compose.yml config --services
```

Ausgabe (stdout, Services in Reihenfolge):

```text
postgres
redis
migrate
llm-orchestrator
news-engine
market-stream
structure-engine
drawing-engine
feature-engine
signal-engine
paper-broker
learning-engine
live-broker
alert-engine
api-gateway
dashboard
monitor-engine
```

Exit-Code: **0**.

Hinweis: Ohne geladene `.env`/`--env-file` meldet Compose Warnungen zu u. a. `POSTGRES_PASSWORD`, `FRONTEND_URL`, `APP_BASE_URL` (Default leer). Für einen echten Start **immer** die passende ENV-Datei setzen (`COMPOSE_ENV_FILE` / `--env-file` wie bei Bootstrap).

### 5.2 Preflight local (Beispiel-ENV)

Befehl:

```text
python tools/compose_start_preflight.py --env-file .env.local.example --profile local
```

Ausgabe (stdout):

```text
compose_start_preflight: OK (local) — 17 Service(s) in der effektiven Compose-Config.
```

Exit-Code: **0**.

### 5.3 Preflight shadow (Beispiel-ENV, nur Basis-YML)

Befehl:

```text
python tools/compose_start_preflight.py --env-file .env.shadow.example --profile shadow
```

Ausgabe (stdout):

```text
compose_start_preflight: OK (shadow) — 17 Service(s) in der effektiven Compose-Config.
```

Exit-Code: **0**.

### 5.4 Definierter Bootstrap-Befehl local

- **Windows:** `pwsh scripts/bootstrap_stack.ps1 local` oder `pnpm bootstrap:local`
- **Unix:** `bash scripts/bootstrap_stack.sh local`

### 5.5 Readiness nach Start (kontrollierter Check)

- **Schnellcheck Gateway:** `curl -fsS --max-time 5 http://127.0.0.1:8000/ready` — erwartet HTTP **200**, wenn `api-gateway` laeuft und bereit ist.
- **Vollstaendig (local mit Publish):** `bash scripts/healthcheck.sh` (alle Engine-URLs auf localhost).
- **Shadow/Production (ohne Worker-Host-Ports):** `HEALTHCHECK_EDGE_ONLY=true bash scripts/healthcheck.sh`

Lauf-Nachweis in dieser Session: `curl` gegen `:8000/ready` endete mit **Timeout** (kein erreichbarer Listener) — plausibel, weil der Stack hier nicht gestartet wurde. Nach erfolgreichem `pnpm dev:up` bzw. Bootstrap erneut ausfuehren.

---

## 6. Geänderte / relevante Artefakte (Sync)

- `scripts/bootstrap_stack.sh`, `scripts/bootstrap_stack.ps1` — Preflight.
- `scripts/dev_up.ps1`, `scripts/dev_down.ps1`, `scripts/dev_reset_db.ps1`, `scripts/dev_status.ps1`, `scripts/dev_logs.ps1`, `scripts/compose_up.ps1` — `Get-DevComposeFileArgs`, Default **mit** `local-publish`.
- `scripts/_dev_compose.ps1` — `Wait-DevStackHealthy` mit `ComposeFileArgs`.
- `tools/compose_start_preflight.py` — Preflight.
- `docs/compose_runtime.md`, `docs/LOCAL_START_MINIMUM.md` — abgeglichen.

---

## 7. Offene Punkte

- `[TECHNICAL_DEBT]` Weitere Hilfsskripte (`rebuild_gateway.ps1`, `close_local_monitor_alerts.ps1`, …) nutzen noch einzelnes `-f docker-compose.yml` — bei Bedarf `-NoLocalPublish`-Parität ergänzen, wenn der Stack mit Overlay läuft.
