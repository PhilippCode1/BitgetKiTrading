# bitget-btc-ai — ENV, Secrets und Authentifizierung (ChatGPT-Übergabe)

**Dokumenttyp:** Konfigurations- und Auth-Matrix für Betrieb und Fehlerdiagnose.  
**Stand:** 2026-04-04.  
**Methodik:** Inhalte aus Repo-Dateien abgeleitet; wo keine direkte Code-/Datei-Prüfung erfolgte, als **nicht verifiziert** markiert.

---

## 1. Gesamtüberblick über das Konfigurationsmodell

| Prinzip                   | Beschreibung                                                                                                                                                                                                                    | Beleg                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Profil-Dateien**        | Laufzeit-ENV kommt aus `.env.local` / `.env.shadow` / `.env.production` / `.env.test` — Vorlagen `*.example`. Katalog: `.env.example` (nicht ungefiltert kopieren).                                                             | `docs/env_profiles.md`, `docs/CONFIGURATION.md` (Verweis in `env_profiles.md`)                                                |
| **Auflösungsreihenfolge** | `CONFIG_ENV_FILE` → `COMPOSE_ENV_FILE` → `ENV_PROFILE_FILE` → `STACK_PROFILE` / `APP_ENV` → Fallback `.env.local`.                                                                                                              | `docs/env_profiles.md`                                                                                                        |
| **Compose**               | `docker-compose.yml` setzt `CONFIG_ENV_FILE` aus `COMPOSE_ENV_FILE` (Default `.env.local`), zusätzlich `env_file:`-Injection.                                                                                                   | `docs/env_profiles.md`, `docker-compose.yml` (`x-app-runtime-env`)                                                            |
| **Kern-Flags**            | `PRODUCTION` (harte Validierung, Secret-Pflicht), `APP_ENV` (`local`/`shadow`/`production`/`test`), `EXECUTION_MODE` (`paper`/`shadow`/`live`).                                                                                 | `docs/env_profiles.md`, `config/settings.py`                                                                                  |
| **Validierung**           | `config/bootstrap.py` → `validate_required_secrets()` nutzt `config/required_secrets_matrix.json`. CLI: `tools/validate_env_profile.py`.                                                                                        | `docs/SECRETS_MATRIX.md`, `config/required_secrets.py`                                                                        |
| **Auth-Schichten**        | (1) Öffentliche Gateway-Pfade z. B. `/health`. (2) Sensible Pfade: JWT `Authorization: Bearer` oder `X-Gateway-Internal-Key` (`GATEWAY_INTERNAL_API_KEY`). (3) Dienst-zu-Dienst: `X-Internal-Service-Key` (`INTERNAL_API_KEY`). | `docs/api_gateway_security.md`, `services/api-gateway/src/api_gateway/auth.py`, `shared/python/src/shared_py/service_auth.py` |
| **Dashboard**             | Next.js **Server** (BFF) trägt `DASHBOARD_GATEWAY_AUTHORIZATION` zum Gateway; Browser bekommt **kein** Gateway-JWT aus diesem Mechanismus.                                                                                      | `docs/api_gateway_security.md`, `apps/dashboard/src/lib/server-env.ts`                                                        |

---

## 2. Tabelle aller kritischen ENV-Variablen

_Auszug der wichtigsten Schlüssel; vollständige Liste siehe `.env.example` und `config/required_secrets_matrix.json`._

### 2.1 Gateway- und Dashboard-Auth

| Variable                                               | Zweck                                                                                        | Typ            |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------- | -------------- |
| `GATEWAY_JWT_SECRET`                                   | HS256-Secret für vom Gateway verifizierte JWTs (u. a. Mint für Dashboard).                   | Secret         |
| `GATEWAY_JWT_AUDIENCE`                                 | JWT `aud` (Default laut Mint-Skript: `api-gateway`).                                         | Konfiguration  |
| `GATEWAY_JWT_ISSUER`                                   | JWT `iss` (Default: `bitget-btc-ai-gateway`).                                                | Konfiguration  |
| `GATEWAY_ENFORCE_SENSITIVE_AUTH`                       | Erzwingt sensibles Auth (zusammen mit `PRODUCTION=true` typisch an).                         | Flag           |
| `GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN`                     | `X-Admin-Token` nur wenn sensibles Auth **nicht** erzwungen und explizit `true`.             | Flag           |
| `GATEWAY_INTERNAL_API_KEY`                             | Header `X-Gateway-Internal-Key` — Gateway-intern/Admin; **nicht** gleich `INTERNAL_API_KEY`. | Secret         |
| `GATEWAY_INTERNAL_KEY_ROLES`                           | CSV Rollen für internen Gateway-Key; leer = volles Default-Set.                              | Konfiguration  |
| `DASHBOARD_GATEWAY_AUTHORIZATION`                      | Vollständiger Header-Wert, z. B. `Bearer <jwt>`, nur **Next-Server** (BFF).                  | Secret / Token |
| `API_GATEWAY_URL`                                      | Basis-URL des Gateways für Server-seitige Requests (`server-env.ts`).                        | URL            |
| `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` | Öffentliche Gateway-/WS-Basis für Client (ohne Secrets).                                     | Öffentlich     |
| `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`                   | Browser-Origin vs. erlaubte CORS-Origins am Gateway.                                         | URL            |
| `GATEWAY_MANUAL_ACTION_SECRET`                         | Optional: Secret für Manual-Action-JWT; sonst Fallback `GATEWAY_JWT_SECRET`.                 | Secret         |

### 2.2 Dienst-zu-Dienst

| Variable                      | Zweck                                                                                            | Typ    |
| ----------------------------- | ------------------------------------------------------------------------------------------------ | ------ |
| `INTERNAL_API_KEY`            | Alias auch `SERVICE_INTERNAL_API_KEY` in `BaseServiceSettings`; Header `X-Internal-Service-Key`. | Secret |
| `LLM_ORCH_BASE_URL`           | Gateway → LLM-Orchestrator HTTP-Basis; leer = aus `HEALTH_URL_LLM_ORCHESTRATOR` ableiten.        | URL    |
| `HEALTH_URL_LLM_ORCHESTRATOR` | u. a. Ableitung der Orchestrator-Basis-URL im Gateway.                                           | URL    |
| `LIVE_BROKER_BASE_URL`        | optional; sonst aus `HEALTH_URL_LIVE_BROKER`.                                                    | URL    |

### 2.3 Datenhaltung und Betrieb

| Variable                          | Zweck                                                                          |
| --------------------------------- | ------------------------------------------------------------------------------ |
| `DATABASE_URL`, `REDIS_URL`       | Verbindungen (Host); in Docker oft `DATABASE_URL_DOCKER` / `REDIS_URL_DOCKER`. |
| `POSTGRES_PASSWORD`               | Compose-Postgres                                                               |
| `BITGET_USE_DOCKER_DATASTORE_DSN` | `true` erzwingt u. a. keine Loopback-`HEALTH_URL_*` im Gateway (Validator).    |

### 2.4 Bitget

| Variable                                                                      | Zweck                                                                                 |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `BITGET_DEMO_ENABLED`                                                         | Demo-Modus; bei `PRODUCTION=true` **verboten** (`config/settings.py`).                |
| `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE`                | Live-Konto REST/WS signiert.                                                          |
| `BITGET_DEMO_API_KEY`, `BITGET_DEMO_API_SECRET`, `BITGET_DEMO_API_PASSPHRASE` | Demo-Konto.                                                                           |
| `BITGET_API_BASE_URL`, `BITGET_WS_PUBLIC_URL`, `BITGET_WS_PRIVATE_URL`        | Endpunkte.                                                                            |
| Weitere `BITGET_*`                                                            | Universum, Scopes, Defaults — siehe `.env.local.example` und `docs/bitget-config.md`. |

**Pydantic-Feld für Live-Keys:** `shared/python/src/shared_py/bitget/config.py` (`BITGET_API_KEY` etc.).

### 2.5 OpenAI / LLM-Orchestrator

| Variable                                                                   | Zweck                                                             |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `OPENAI_API_KEY`                                                           | Provider-Key im **llm-orchestrator** (`LLMOrchestratorSettings`). |
| `LLM_USE_FAKE_PROVIDER`                                                    | Deterministische Antworten; bei `PRODUCTION=true` verboten.       |
| `OPENAI_MODEL_PRIMARY`, `OPENAI_MODEL_HIGH_REASONING`, `OPENAI_MODEL_FAST` | Modellwahl.                                                       |

### 2.6 Weitere Secrets (Auswahl)

| Variable                                                    | Kontext                                                         |
| ----------------------------------------------------------- | --------------------------------------------------------------- |
| `ADMIN_TOKEN`, `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY` | Operator-/App-Legacy laut `docs/SECRETS_MATRIX.md`              |
| `COMMERCIAL_METER_SECRET`                                   | Meter-Ingest `X-Commercial-Meter-Secret`                        |
| `TELEGRAM_BOT_TOKEN`                                        | Alert-Engine                                                    |
| `STRIPE_*`                                                  | Commerce (wenn aktiv)                                           |
| `PAYMENT_MOCK_WEBHOOK_SECRET`                               | Dashboard-Server + Gateway (Mock) laut `docs/SECRETS_MATRIX.md` |

---

## 3. Wer liest welche Variable

| Variable                                                           | Primäre Leser (verifiziert im Repo)                                                                                                                                                                                                                   |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DASHBOARD_GATEWAY_AUTHORIZATION`                                  | Next.js **Server**: `apps/dashboard/src/lib/server-env.ts` (`readGatewayAuthHeader`); BFF-Routen unter `apps/dashboard/src/app/api/dashboard/`.                                                                                                       |
| `API_GATEWAY_URL`                                                  | Next.js **Server**: `apps/dashboard/src/lib/server-env.ts` (`readApiGatewayUrl`); Fehlertexte u. a. `gateway-upstream.ts`, `gateway-bootstrap-probe.ts`.                                                                                              |
| `NEXT_PUBLIC_*`                                                    | Next.js **Client und Build**: `apps/dashboard/src/lib/env.ts` u. a.                                                                                                                                                                                   |
| `GATEWAY_JWT_SECRET`, `GATEWAY_JWT_AUDIENCE`, `GATEWAY_JWT_ISSUER` | **API-Gateway** `GatewaySettings` / `auth.py`; **Mint-Skript** `scripts/mint_dashboard_gateway_jwt.py`.                                                                                                                                               |
| `GATEWAY_INTERNAL_API_KEY`                                         | **API-Gateway** `auth.py` (`X-Gateway-Internal-Key`).                                                                                                                                                                                                 |
| `INTERNAL_API_KEY` (`service_internal_api_key`)                    | **Alle** Python-Services mit `BaseServiceSettings`; **Gateway** Forward: `llm_orchestrator_forward.py`, `live_broker_forward.py`; **llm-orchestrator**, **live-broker**, **monitor-engine**, **alert-engine** laut `docs/INTERNAL_SERVICE_ROUTES.md`. |
| `LLM_ORCH_BASE_URL`, `HEALTH_URL_LLM_ORCHESTRATOR`                 | **API-Gateway** `config/gateway_settings.py` (`llm_orchestrator_http_base()`).                                                                                                                                                                        |
| `OPENAI_API_KEY`, `LLM_USE_FAKE_PROVIDER`                          | **llm-orchestrator** `services/llm-orchestrator/src/llm_orchestrator/config.py`.                                                                                                                                                                      |
| `BITGET_API_KEY` / Demo-Varianten                                  | **shared_py** `shared/python/src/shared_py/bitget/config.py`; Nutzung in **live-broker** (`exchange_client.py`, `config.py`), **market-stream** (indirekt über Bitget-Client — **nicht verifiziert:** jede einzelne Importstelle in diesem Schritt).  |

---

## 4. Welche Variablen im Browser niemals landen dürfen

| Kategorie              | Beispiele                                                                                                                                                                                                     | Regel                                                                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Explizit verboten**  | `GATEWAY_JWT_SECRET`, `INTERNAL_API_KEY`, `GATEWAY_INTERNAL_API_KEY`, `OPENAI_API_KEY`, `BITGET_API_*`, `DASHBOARD_GATEWAY_AUTHORIZATION`, `COMMERCIAL_METER_SECRET`, `TELEGRAM_BOT_TOKEN`, `STRIPE_SECRET_*` | Nur Server-ENV oder Worker-Container; **niemals** `NEXT_PUBLIC_*` präfixieren.                                                                                     |
| **Erlaubt öffentlich** | `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`, Feature-Flags ohne Geheimnis                                                                                                                           | In `apps/dashboard/src/lib/env.ts`; Production: keine stillen Localhost-Fallbacks laut Kommentar in `env.ts` / `server-env.ts`.                                    |
| **Rustung**            | `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true`                                                                                                                                                                     | Sensible `/v1`-Pfade über BFF statt Browser→Gateway mit JWT im Client; **verifiziert:** `docs/api_gateway_security.md`, `apps/dashboard/src/lib/env.ts` Kommentar. |

---

## 5. JWT- und interne Key-Flüsse

### 5.1 Dashboard → Gateway (Operator-Konsole, BFF)

| Schritt | Was passiert                                                                                                               |
| ------- | -------------------------------------------------------------------------------------------------------------------------- |
| 1       | Operator nutzt UI; Anfragen gehen an `/api/dashboard/...` (Next Route Handlers).                                           |
| 2       | Server liest `DASHBOARD_GATEWAY_AUTHORIZATION` und `API_GATEWAY_URL`.                                                      |
| 3       | Request ans Gateway mit Header `Authorization: <exakt der Wert aus DASHBOARD_GATEWAY_AUTHORIZATION>` (typisch `Bearer …`). |
| 4       | Gateway prüft JWT mit `GATEWAY_JWT_SECRET` / Audience / Issuer und Rollen (`gateway_roles` / `scope`).                     |

**Mint:** `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file` — liest `GATEWAY_JWT_SECRET`, schreibt optional `DASHBOARD_GATEWAY_AUTHORIZATION=Bearer …`. **verifiziert:** `scripts/mint_dashboard_gateway_jwt.py`.

### 5.2 Gateway interner Admin-Key

| Header                   | ENV                        | Rolle                                                                                 |
| ------------------------ | -------------------------- | ------------------------------------------------------------------------------------- |
| `X-Gateway-Internal-Key` | `GATEWAY_INTERNAL_API_KEY` | Gateway-eigener Schlüssel mit konfigurierbaren Rollen (`GATEWAY_INTERNAL_KEY_ROLES`). |

**verifiziert:** `docs/api_gateway_security.md`, `services/api-gateway/src/api_gateway/auth.py` (`_HEADER_INTERNAL`).

### 5.3 Gateway → LLM-Orchestrator / live-broker

| Header                   | ENV                                                       | Pflicht                                                                                                                                                                                    |
| ------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `X-Internal-Service-Key` | `INTERNAL_API_KEY` (Pydantic: `service_internal_api_key`) | Wenn Key gesetzt **oder** `PRODUCTION=true`: mismatch → **401** `INTERNAL_AUTH_REQUIRED`; in Prod ohne Key → **503** `INTERNAL_AUTH_MISCONFIGURED` (siehe `assert_internal_service_auth`). |

**Forward-URL LLM:** `settings.llm_orchestrator_http_base()` — `LLM_ORCH_BASE_URL` oder aus `HEALTH_URL_LLM_ORCHESTRATOR`. Fehler ohne Basis: `RuntimeError` in `post_llm_orchestrator_json`. **verifiziert:** `services/api-gateway/src/api_gateway/llm_orchestrator_forward.py`, `config/gateway_settings.py`.

**Gleicher `INTERNAL_API_KEY`-Wert** muss im **llm-orchestrator** (und anderen geschützten Diensten) konfiguriert sein wie im Gateway. **verifiziert:** `shared_py/service_auth.py`, `API_INTEGRATION_STATUS.md`.

---

## 6. Häufigste echte Fehlkonfigurationen

| #   | Fehlkonfiguration                                                                                                               | Warum problematisch                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 1   | `HEALTH_URL_*` / `LLM_ORCH_BASE_URL` mit `localhost` im **Docker-Container** Gateway bei `BITGET_USE_DOCKER_DATASTORE_DSN=true` | Validator schlägt fehl oder falsche Ziele.        |
| 2   | `INTERNAL_API_KEY` im Gateway ≠ Orchestrator (oder einer leer in Prod)                                                          | 401/503 auf LLM-Forward.                          |
| 3   | `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt, abgelaufen, oder Next nicht neu gestartet                                              | BFF **503**.                                      |
| 4   | `GATEWAY_JWT_SECRET` geändert, JWT nicht neu gemint                                                                             | Gateway **401** für Dashboard-BFF.                |
| 5   | `API_GATEWAY_URL` zeigt vom Next-Host aus nicht erreichbare Adresse (Container vs. Host)                                        | 502 / Netzwerkfehler.                             |
| 6   | `GATEWAY_INTERNAL_API_KEY` mit `INTERNAL_API_KEY` verwechselt                                                                   | Falsche Header / Auth schlägt fehl.               |
| 7   | `OPENAI_API_KEY` fehlt, `LLM_USE_FAKE_PROVIDER=false`                                                                           | LLM-502 über Gateway.                             |
| 8   | Bitget Live-Keys leer, aber Live-Pfade aktiv                                                                                    | Exchange-Fehler / No-Trade je nach Service.       |
| 9   | `PRODUCTION=true` mit `API_AUTH_MODE=none` oder Demo/Fake-Flags                                                                 | Validierung in `config/settings.py` schlägt fehl. |

---

## 7. Symptome im UI, Gateway und Service-Log

| Symptom                                          | Wo sichtbar             | Typische technische Ursache                                                                                          |
| ------------------------------------------------ | ----------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Konsole leer, „Gateway-Autorisierung“            | Dashboard UI / BFF JSON | `DASHBOARD_GATEWAY_AUTHORIZATION` fehlt                                                                              |
| HTTP **503** auf `/api/dashboard/*`              | Browser (Netzwerk-Tab)  | `API_GATEWAY_URL` fehlt (Production) oder JWT fehlt — Texte in `gateway-bootstrap-probe.ts`, `edge-status/route.ts`  |
| **401** auf sensiblen Gateway-Routen             | Gateway-Antwort         | JWT ungültig/falsch Secret/fehlende Rolle                                                                            |
| **502** LLM Operator Explain                     | UI + Gateway-Logs       | Orchestrator down, `OPENAI_API_KEY`, oder interner Key — **verifiziert:** Kommentar in `llm_orchestrator_forward.py` |
| Gateway-Log **401** mit `INTERNAL_AUTH_REQUIRED` | Gateway → Upstream      | Falscher/fehlender `X-Internal-Service-Key`                                                                          |
| **503** `INTERNAL_AUTH_MISCONFIGURED`            | Interne APIs            | `PRODUCTION=true`, `INTERNAL_API_KEY` leer                                                                           |
| CORS-Fehler im Browser                           | Browser-Konsole         | `CORS_ALLOW_ORIGINS` / `FRONTEND_URL` passen nicht zur Origin                                                        |
| Compose-Start scheitert Gateway-Validierung      | Container-Logs          | Loopback-URLs bei Docker-DSN                                                                                         |

---

## 8. Fix-Anleitung je häufigem Fehler

| Problem                       | Schritte                                                                                                                                                                                     |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----------- |
| **BFF 503 „Authorization“**   | 1) `GATEWAY_JWT_SECRET` in `.env.local` prüfen. 2) `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`. 3) **Next.js / Dashboard-Container neu starten**. |
| **INTERNAL_API_KEY mismatch** | Gleichen Wert in **allen** betroffenen Services (Gateway, llm-orchestrator, live-broker, …) setzen; Compose neu hochfahren.                                                                  |
| **LLM: Basis-URL fehlt**      | Im Gateway: `LLM_ORCH_BASE_URL` **oder** `HEALTH_URL_LLM_ORCHESTRATOR` mit `http://llm-orchestrator:8070/ready` (Compose-Beispiel in `docker-compose.yml`).                                  |
| **API_GATEWAY_URL**           | Host-Dev: `http://127.0.0.1:8000`. Dashboard-Container: typisch `http://api-gateway:8000` (siehe `docker-compose.yml` `dashboard.environment`).                                              |
| **Shadow/Prod Healthcheck**   | `HEALTHCHECK_EDGE_ONLY=true` für `scripts/healthcheck.sh`, wenn keine Worker-Ports auf dem Host — `docs/compose_runtime.md`.                                                                 |
| **ENV-Profil prüfen**         | `python tools/validate_env_profile.py --env-file <datei> --profile local                                                                                                                     | staging | production` |
| **OpenAI**                    | Key nur im **llm-orchestrator**-Prozess; lokal alternativ `LLM_USE_FAKE_PROVIDER=true` (nicht Shadow/Prod).                                                                                  |

---

## 9. Unterschiede zwischen Local, Shadow/Staging und Produktion

| Aspekt                 | Local (`.env.local`)                                                        | Shadow / Staging (`.env.shadow`, `APP_ENV=shadow`)                                  | Production (`.env.production`)              |
| ---------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------- |
| `PRODUCTION`           | typisch `false`                                                             | `true`                                                                              | `true`                                      |
| Demo/Fake              | `BITGET_DEMO_ENABLED`, `LLM_USE_FAKE_PROVIDER`, `NEWS_FIXTURE_MODE` erlaubt | **verboten** (`config/settings.py` `_prod_safety`)                                  | **verboten**                                |
| Gateway sensibles Auth | oft `GATEWAY_ENFORCE_SENSITIVE_AUTH=false` möglich                          | typisch erzwungen; `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY` Pflicht | gleich                                      |
| `INTERNAL_API_KEY`     | optional → lokaler Bypass laut `service_auth.py`                            | in Prod-Pfaden erforderlich für geschützte interne Routen                           | erforderlich                                |
| URLs                   | `localhost` möglich                                                         | öffentliche URLs ohne Platzhalter-Substrings                                        | TLS/HSTS-Regeln laut `docs/env_profiles.md` |
| Validierung CLI        | `--profile local`                                                           | `--profile staging` (Matrix-Spalte „staging“ = operativ Shadow)                     | `--profile production`                      |

**Maschinenlesbare Pflichtkeys:** `config/required_secrets_matrix.json` — Spalten `local` / `staging` / `production`. **verifiziert:** `docs/SECRETS_MATRIX.md`.

---

## 10. Übergabe an ChatGPT

1. **Zwei verschiedene „interne“ Keys:** `GATEWAY_INTERNAL_API_KEY` (Gateway-Admin, Header `X-Gateway-Internal-Key`) vs. `INTERNAL_API_KEY` (Dienst-zu-Dienst, `X-Internal-Service-Key`) — niemals vermischen.
2. **Dashboard-Auth** ist **serverseitig** `DASHBOARD_GATEWAY_AUTHORIZATION`; Diagnose über `GET /api/dashboard/edge-status` und Gateway-Logs.
3. Bei Docker: **Loopback-URLs** in `HEALTH_URL_*` / `LLM_ORCH_BASE_URL` für Gateway mit `BITGET_USE_DOCKER_DATASTORE_DSN=true` sind **falsch** — Docker-Dienstnamen verwenden.
4. Immer `docs/api_gateway_security.md` und `docs/SECRETS_MATRIX.md` als Kanon lesen; Matrix-JSON für exakte Pflicht pro Profil.
5. Bitget- und OpenAI-Keys **nie** als `NEXT_PUBLIC_*`.

---

## 11. Anhang mit Dateipfaden und belegenden Codestellen

| Thema                                         | Pfad(e)                                                                                                                                                        |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gateway-Auth, Rollen, JWT                     | `services/api-gateway/src/api_gateway/auth.py`                                                                                                                 |
| Gateway Settings / `HEALTH_URL_*` / LLM-Basis | `config/gateway_settings.py`                                                                                                                                   |
| Interner Service-Key Semantik                 | `shared/python/src/shared_py/service_auth.py`                                                                                                                  |
| LLM-Forward + Fehlermeldungen                 | `services/api-gateway/src/api_gateway/llm_orchestrator_forward.py`                                                                                             |
| Live-Broker-Forward                           | `services/api-gateway/src/api_gateway/live_broker_forward.py`                                                                                                  |
| Dashboard Server-ENV                          | `apps/dashboard/src/lib/server-env.ts`                                                                                                                         |
| Dashboard Client public ENV                   | `apps/dashboard/src/lib/env.ts`                                                                                                                                |
| BFF Fehlermeldungen / Probes                  | `apps/dashboard/src/lib/gateway-bootstrap-probe.ts`, `apps/dashboard/src/lib/gateway-upstream.ts`, `apps/dashboard/src/app/api/dashboard/edge-status/route.ts` |
| JWT minten                                    | `scripts/mint_dashboard_gateway_jwt.py`                                                                                                                        |
| LLM-Orchestrator Settings                     | `services/llm-orchestrator/src/llm_orchestrator/config.py`                                                                                                     |
| Bitget API-Felder                             | `shared/python/src/shared_py/bitget/config.py`                                                                                                                 |
| Basis-Settings + `INTERNAL_API_KEY` Alias     | `config/settings.py` (`service_internal_api_key`, `AliasChoices`)                                                                                              |
| Pflicht-Secrets JSON                          | `config/required_secrets_matrix.json`                                                                                                                          |
| Interne Routen Inventar                       | `docs/INTERNAL_SERVICE_ROUTES.md`                                                                                                                              |
| Secret-Übersicht                              | `docs/SECRETS_MATRIX.md`                                                                                                                                       |
| Gateway-Sicherheit ausführlich                | `docs/api_gateway_security.md`                                                                                                                                 |
| ENV-Profile                                   | `docs/env_profiles.md`                                                                                                                                         |
| Integrations-Fehlerbilder                     | `API_INTEGRATION_STATUS.md`                                                                                                                                    |
| ENV-Vorlagen                                  | `.env.local.example`, `.env.shadow.example`, `.env.production.example`, `.env.example`                                                                         |

---

_Ende der Übergabedatei._
