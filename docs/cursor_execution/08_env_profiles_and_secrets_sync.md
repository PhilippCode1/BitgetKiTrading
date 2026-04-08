# 08 — ENV-Profile, Matrix und Secrets (Synchronisation)

**Ziel:** Eine nachvollziehbare, technisch konsistente Spur von der Auth-/ENV-Matrix über `required_secrets_matrix.json`, die Profil-Beispiel-Dateien, `validate_env_profile.py` bis zu den Dashboard-Server-Settings.

**Pflichtgrundlage:** `docs/chatgpt_handoff/03_ENV_SECRETS_AUTH_MATRIX.md`

**Stand:** 2026-04-05 (Repo-Sync)

---

## 1. Harmonisierte Variablen (Kern)

| Variable                                                         | Rolle                                                                                        | Leser (Kurz)                                         |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `API_GATEWAY_URL`                                                | Next.js **Server** → Gateway (BFF-Upstream)                                                  | `apps/dashboard/src/lib/server-env.ts`               |
| `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL`           | **Browser**/Build — nur öffentliche Basis-URLs                                               | `apps/dashboard/src/lib/env.ts`                      |
| `DASHBOARD_GATEWAY_AUTHORIZATION`                                | Vollständiger `Authorization`-Header zum Gateway, **nur Server**                             | `server-env.ts`                                      |
| `GATEWAY_JWT_SECRET`                                             | HS256 für vom Gateway verifizierte JWTs; Mint für Dashboard                                  | Gateway, `scripts/mint_dashboard_gateway_jwt.py`     |
| `GATEWAY_INTERNAL_API_KEY`                                       | Header `X-Gateway-Internal-Key` — **Gateway-eigen**, nicht Dienst-zu-Dienst                  | Gateway `auth.py`                                    |
| `INTERNAL_API_KEY`                                               | Header `X-Internal-Service-Key`; Alias **`SERVICE_INTERNAL_API_KEY`** (Pydantic)             | Gateway-Forward, Worker, `shared_py/service_auth.py` |
| `LLM_ORCH_BASE_URL`                                              | Gateway → LLM-Orchestrator HTTP-Basis; leer möglich wenn `HEALTH_URL_LLM_ORCHESTRATOR` setzt | `config/gateway_settings.py`                         |
| `HEALTH_URL_LLM_ORCHESTRATOR`                                    | Readiness-URL; Gateway leitet bei fehlender `LLM_ORCH_BASE_URL` Host/Port ab                 | `gateway_settings.py`                                |
| `LLM_ORCH_URL`                                                   | **Kein** Gateway-Feld: Basis für `scripts/healthcheck.sh` (`…/ready`)                        | `scripts/healthcheck.sh`                             |
| `REDIS_URL` / `REDIS_URL_DOCKER`                                 | Host- vs. Container-Sicht                                                                    | Matrix: beide Pflicht (wie DB-URLs)                  |
| `DATABASE_URL` / `DATABASE_URL_DOCKER`                           | Host- vs. Container-Sicht                                                                    | Matrix                                               |
| `OPENAI_API_KEY`                                                 | Im **llm-orchestrator**; bei Shadow/Prod ohne Fake-Provider Pflicht (bedingt im Validator)   | `llm_orchestrator/config.py`                         |
| `BITGET_API_KEY` / `BITGET_API_SECRET` / `BITGET_API_PASSPHRASE` | Live-Konto; bedingt wenn `LIVE_TRADE_ENABLE=true` und kein Demo                              | `shared_py/bitget/config.py`                         |
| `BITGET_DEMO_*`                                                  | Nur wenn `BITGET_DEMO_ENABLED=true` (nicht Production/Shadow)                                | Handoff §2.4                                         |

---

## 2. Matrix (`config/required_secrets_matrix.json`)

- **Profil-Mapping CLI:** `local` → Spalte `local`; `staging` **oder** `shadow` → Spalte `staging`; `production` → `production` (`config/required_secrets.py`: `required_env_names_for_env_file_profile`).
- **Service-Boot:** `validate_required_secrets` nutzt dieselbe Matrix-Spalte je nach `production` und `APP_ENV` (`_matrix_phase_for_boot`).
- Aktuelle **Pflicht-Keys** für ENV-Datei-Validierung (Union, alle `required` in der jeweiligen Spalte): u. a. `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_DOCKER`, `REDIS_URL`, `REDIS_URL_DOCKER`, `JWT_SECRET`, `SECRET_KEY`, `ADMIN_TOKEN`, `ENCRYPTION_KEY`, `INTERNAL_API_KEY`, `GATEWAY_JWT_SECRET`, `API_GATEWAY_URL`, `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`, `DASHBOARD_GATEWAY_AUTHORIZATION` (local optional; Shadow/Prod required).

---

## 3. Verbote und Regeln

### 3.1 `NEXT_PUBLIC_*`

- **Niemals** Secrets oder server-only Namen unter `NEXT_PUBLIC_` prefixen (OpenAI, Bitget-Keys, Gateway-JWT, interne Service-Keys, Dashboard-Gateway-Auth, Stripe-Secrets, …).
- Prüfung: `tools/validate_env_profile.py` → `next_public_secret_key_issues()` (Substring-Blockliste auf **Schlüsselnamen**).
- Detailtabelle: Handoff **§4**.

### 3.2 Shadow / Production

- `LLM_USE_FAKE_PROVIDER=true` verboten (Validator + `config/settings.py`).
- `OPENAI_API_KEY` erforderlich, wenn prod-like und kein Fake (Validator: `conditional_env_issues`).
- `INTERNAL_API_KEY` mindestens 16 Zeichen, keine offensichtlichen Weak-Wörter (`bootstrap_env_consistency_issues`).
- `HEALTH_URL_*` / `LLM_ORCH_BASE_URL`: kein Host-Loopback in Container-Kontext (prod-like), siehe `bootstrap_env_checks.py`.
- Gateway→LLM: mindestens **eine** gültige von `LLM_ORCH_BASE_URL` oder `HEALTH_URL_LLM_ORCHESTRATOR` (Validator: `llm_gateway_base_issues`).

---

## 4. Beispiel-ENV-Dateien

| Datei                     | Zweck                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `.env.example`            | Vollkatalog, Platzhalter `<SET_ME>` — **nicht** ungefiltert kopieren                                                        |
| `.env.local.example`      | Local; Matrix-Pflichtzeilen mit `example_only_*` damit `validate_env_profile --profile local` auf der Vorlage lauffähig ist |
| `.env.shadow.example`     | Shadow; `shadow_ex_only_*` / `sk-example-openai-…` — vor Deploy ersetzen                                                    |
| `.env.production.example` | Production; `prod_ex_only_*` — vor Deploy ersetzen                                                                          |

**Drift:** `LLM_ORCH_URL` bleibt absichtlich für Healthcheck-Skripte; Gateway nutzt `LLM_ORCH_BASE_URL` + `HEALTH_URL_LLM_ORCHESTRATOR` (Handoff §2.2 / §5.3).

---

## 5. Validierung (Nachweise)

Empfohlene Befehle:

```bash
python tools/validate_env_profile.py --env-file .env.local --profile local
python tools/validate_env_profile.py --env-file .env.shadow.example --profile staging
python tools/validate_env_profile.py --env-file .env.production.example --profile production
```

- Shadow-Datei: CLI-Profil **`staging`** (entspricht Matrix-Spalte `staging`; Alias `shadow` in `required_secrets.py`).
- Lokal nach JWT-Mint: `--with-dashboard-operator` zusätzlich, um `DASHBOARD_GATEWAY_AUTHORIZATION` zu erzwingen.

**Ergebnis (Stand Repo nach Sync):** Die drei Befehle oben mit `.env.local.example` / `.env.shadow.example` / `.env.production.example` sollen **exit 0** liefern; echte `.env.local` des Operators kann abweichen, muss aber dieselben Pflichtkeys füllen.

---

## 6. Bekannte offene Punkte

- `[TECHNICAL_DEBT]` Matrix kennt keine „pro Service“-Filterung für die **CLI**-Validierung — es ist die Vereinigung aller `required`-Einträge der Profilspalte.
- `[PROVISIONAL]` `GATEWAY_INTERNAL_API_KEY` ist in der Matrix nicht als eigener Pflicht-Eintrag modelliert; sensibles Auth läuft über JWT und optional internen Key (Handoff §5).
