# Lokaler Minimal-Start (Paper, Windows / Docker / WSL)

Ziel (**Roadmap / frischer Clone**): Stack laeuft, **API-Gateway** und **Dashboard** antworten; Operator-Health im Browser **ohne 503** durch fehlendes `DASHBOARD_GATEWAY_AUTHORIZATION`; `GET /v1/system/health` mit gueltigem **Operator-JWT** liefert **HTTP 200**.

**Referenzpfad (eine Standardvariante):** `pnpm dev:up` unter Windows (PowerShell). Das Skript validiert `.env.local`, **schreibt `DASHBOARD_GATEWAY_AUTHORIZATION`** per `mint_dashboard_gateway_jwt.py`, validiert erneut (inkl. Operator-JWT), fuehrt **`tools/compose_start_preflight.py`** aus (Compose-Config + `POSTGRES_PASSWORD`-Heuristik), startet **`docker-compose.yml` + `docker-compose.local-publish.yml`** (Host-Publish der Worker-Ports wie `bootstrap_stack.sh local`) und wartet auf Docker-Healthchecks. Nur Edge-Ports wie Shadow/Prod: `pnpm dev:up -- -NoLocalPublish`. Alternativen (gestaffelt): `pnpm bootstrap:local` bzw. WSL `bash scripts/start_local.sh`. Ueberblick Pflicht-ENV: **[CONFIGURATION.md](CONFIGURATION.md)**.

**Wenn Health im Browser „offline“ wirkt, Gateway aber laufen sollte:** `pnpm local:doctor` (prueft `.env.local`, JWT-Plausibilitaet, `API_GATEWAY_URL` inkl. Host-vs-Docker-Hinweis, `GET /health` und `/ready` **vom gleichen Rechner** wie der Doctor — entspricht dem Next.js-Host ausserhalb von Docker).

## 0. Frischer Clone (Checkliste)

```powershell
git clone <repo-url> bitget-btc-ai
cd bitget-btc-ai
Copy-Item .env.local.example .env.local
# Pflichtwerte in .env.local setzen (siehe Abschnitt 2)
python tools/validate_env_profile.py --env-file .env.local --profile local
pnpm install
```

JWT fuer das Dashboard: **bei `pnpm dev:up` automatisch** (oder manuell einmalig):

```powershell
python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file
python tools/validate_env_profile.py --env-file .env.local --profile local --with-dashboard-operator
```

Dann Stack starten (Abschnitt 4). **Nur** wenn du das Dashboard **ausserhalb** von Docker mit `pnpm dev` startest: nach Mint oder Aenderung an `DASHBOARD_GATEWAY_AUTHORIZATION` den Next-Prozess **neu starten** (ENV wird nur beim Start geladen).

## 1. Voraussetzungen

- **Docker Desktop** (Windows) bzw. Docker unter Linux/WSL2
- **Node** + **pnpm** (siehe Root-[README.md](../README.md))
- **Python 3.11+** im `PATH` (JWT-Mint, `validate_env_profile`, Smoke)

### Optional WSL (Linux-Bash)

Dieselbe Logik wie unter Windows; Repo in der WSL-Distro klonen, Docker-Integration aktivieren.

```bash
cp .env.local.example .env.local
# Werte setzen, dann:
python3 tools/validate_env_profile.py --env-file .env.local --profile local
pnpm install
bash scripts/start_local.sh
# start_local.sh -> bootstrap_stack.sh local: mintet JWT, staged Compose + Migrationen, Host-Ports (local-publish)
```

Smoke: `bash scripts/rc_health.sh` (laedt `.env.local` analog zu `pnpm smoke`).

## 2. ENV anlegen (.env.local)

```powershell
Copy-Item .env.local.example .env.local
```

**Pflicht ersetzen (keine `<SET_ME>` / leer):**

| Variable                                                                        | Hinweis                                                                                                                                              |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POSTGRES_PASSWORD`                                                             | Ein Passwort; in `DATABASE_URL` und `DATABASE_URL_DOCKER` konsistent verwenden (Vorlage ersetzt oft nur `POSTGRES_PASSWORD`-Platzhalter in den URLs) |
| `DATABASE_URL`, `REDIS_URL`                                                     | Host-Zugriff vom Rechner (typisch `localhost`/`127.0.0.1`); Docker-URLs `*_DOCKER` fuer Services im Compose                                          |
| `GATEWAY_JWT_SECRET`                                                            | Mindestens 32 Zeichen, zufaellig                                                                                                                     |
| `JWT_SECRET`, `SECRET_KEY`, `ADMIN_TOKEN`, `ENCRYPTION_KEY`, `INTERNAL_API_KEY` | Starke Werte                                                                                                                                         |
| `GATEWAY_JWT_SECRET` (Gateway)                                                  | Nur api-gateway braucht ihn zwingend fuer Mint; steht in gemeinsamer `.env.local`                                                                    |

Maschinenlesbare Matrix: [SECRETS_MATRIX.md](SECRETS_MATRIX.md), `config/required_secrets_matrix.json`.

### Paper ohne Live-Bitget (optional)

- `EXECUTION_MODE=paper`, `LIVE_TRADE_ENABLE=false`, `LIVE_BROKER_ENABLED=false` (wie in der Vorlage ueblich).
- Statt echter Live-Keys: `BITGET_DEMO_ENABLED=true` und die drei `BITGET_DEMO_*`-Credentials setzen, **oder** oeffentliche Marktdaten nur — je nachdem welche Services du startest; `market-stream` erwartet typischerweise erreichbare Bitget-Endpunkte (Demo oder oeffentlich).

## 3. Dashboard → Gateway (Server-JWT)

Server-Components (Console, **Health**, BFF) rufen das Gateway mit `DASHBOARD_GATEWAY_AUTHORIZATION` auf (Bearer-JWT). `GATEWAY_JWT_SECRET` in `.env.local` muss mit dem Gateway uebereinstimmen.

- **Windows `pnpm dev:up`:** JWT wird vor `docker compose up` in `.env.local` geschrieben (`-NoMint` zum Ueberspringen).
- **WSL `bootstrap_stack.sh local`:** ebenfalls automatisches Mint vor dem Start.
- **Manuell:** `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`

Danach bei **lokalem** `pnpm dev` (Next auf dem Host) den Prozess neu starten. Der **Dashboard-Container** liest die aktualisierte Datei beim naechsten `docker compose up` (bzw. nach Recreate).

`dev_up.ps1` warnt, falls die Zeile nach Mint weiterhin fehlt (z. B. fehlerhafte Datei).

## 4. Stack starten

**Variante A — Referenz (ein Befehl, JWT-Mint, Healthchecks, Browser):**

```powershell
pnpm dev:up
```

Optional frische DB: `pnpm dev:up -- -ResetDb`  
Smoke direkt: `pnpm dev:up -- -Smoke` oder danach `pnpm smoke`.  
Nur Gateway/Dashboard auf dem Host (ohne Engine-Publish): `pnpm dev:up -- -NoLocalPublish`.

**Variante B — gestaffelter Bootstrap (lokal inkl. Publish-Overlay fuer Engine-Ports auf dem Host):**

```powershell
pnpm bootstrap:local
```

Entspricht `pwsh scripts/bootstrap_stack.ps1 local` (JWT-Mint, Migrationen, gestaffeltes `up`, abschliessend `healthcheck.sh`). Nutze B, wenn du Services direkt am Host-Port debuggen willst; fuer den normalen **Dashboard+Gateway-Alltag** reicht Variante A.

## 5. Akzeptanztests (Roadmap)

### A) API-Gateway: `GET /v1/system/health` mit Operator-JWT → 200

Token aus derselben Basis wie das Dashboard (nur der JWT-Teil):

```powershell
$token = python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/system/health" `
  -Headers @{ Authorization = "Bearer $token" }
```

Erwartung: **HTTP 200**, JSON mit u. a. `execution`, `warnings`, `services` (kein 401/403).

### B) Dashboard Health-Seite ohne 503 (BFF)

- Browser: `http://127.0.0.1:3000` → Operator-Console → **Health**
- Keine Meldung, dass `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt; PDF-Link `/api/dashboard/health/operator-report` liefert keinen **503** aus dem BFF wegen fehlender Auth.

### C) Weitere Schnelltests

- `http://127.0.0.1:8000/ready` → `ready: true`
- `GET /api/dashboard/edge-status` (Dashboard) → `gatewayHealth: ok`, bei gesetztem Auth sinnvoller `operatorHealthProbe`

## 5b. Dashboard: Degradation / Hinweise (Kerzen, Signale, News, Alerts)

| Hinweis                       | Typische Ursache                                                             | Massnahme                                                                                                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Kerzendaten veraltet          | market-stream schreibt keine 1m-Kerzen (fehlende Bitget-Demo-Keys, Netzwerk) | `BITGET_DEMO_*` in `.env.local` setzen, `BITGET_SYMBOL=BTCUSDT`, `docker compose restart market-stream`; optional `DATA_STALE_WARN_MS` erhoehen (siehe `.env.local.example`)         |
| Kein Signal                   | Pipeline braucht frische Kerzen + feature/structure/drawing                  | 5–15 Min warten; `signal-engine` / `market-stream` Logs; Symbole in `SIGNAL_SCOPE_SYMBOLS`                                                                                           |
| News veraltet                 | `NEWS_FIXTURE_MODE=true` ohne frische Fixtures oder fehlende News-APIs       | Echte Keys + `NEWS_FIXTURE_MODE=false` oder Fixture-Ingest triggern                                                                                                                  |
| Viele offene Monitor-Alerts   | Erster Start, Live-Broker oeffentliche Probe, Stale-Daten                    | Logs pruefen; lokal: `pnpm alerts:close-local` oder `pnpm alerts:close-local-all` (nur Dev; **nicht** bei `PRODUCTION=true` / Shadow-Profil). `AllOpen` erfordert `-Force` im Skript |
| Live-Broker / Exchange-Health | Optional lokal abschalten                                                    | `LIVE_REQUIRE_EXCHANGE_HEALTH=false` (in `.env.local.example` bereits fuer Paper)                                                                                                    |

## 6. Smoke nach dem Start (Release-Gate)

```powershell
pnpm smoke
```

(Entspricht `pnpm rc:health` — prueft Gateway, Dashboard und aggregiertes `/v1/system/health` inkl. Lesepfade. Unter Linux/macOS/WSL: `bash scripts/rc_health.sh`.)

Bei **401/403**: `DASHBOARD_GATEWAY_AUTHORIZATION` in `.env.local` setzen (Mint) und Dashboard-Stack neu starten; Hinweise am Ende der Skript-Ausgabe.

## Siehe auch

- [OPS_QUICKSTART.md](OPS_QUICKSTART.md)
- [SECRETS_MATRIX.md](SECRETS_MATRIX.md)
- [env_profiles.md](env_profiles.md)
