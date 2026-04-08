# Konfiguration: ein Modell, klare Pflichten, Fail-fast

Dieses Dokument ergänzt **`docs/env_profiles.md`** (Profilsemantik) und **`docs/SECRETS_MATRIX.md`** (Matrix-Details).

## Zentrale Quellen

| Quelle                                                                                          | Rolle                                                                                        |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **`config/required_secrets_matrix.json`**                                                       | Maschinenlesbare Pflicht-ENV je Phase (`local` / `staging` / `production`)                   |
| **`tools/validate_env_profile.py`**                                                             | CLI-Validierung einer `.env*`-Datei vor dem Start                                            |
| **`scripts/_dev_compose.ps1`**, **`dev_up.ps1`**, **`compose_up.ps1`**, **`bootstrap_stack.*`** | Rufen die Validierung (und lokal: JWT-Mint) vor Docker Compose auf                           |
| **`apps/dashboard/instrumentation.ts`** + **`src/lib/runtime-env-gate.ts`**                     | Beim **Production**-Start von Next: harte Prüfung von Gateway- und `NEXT_PUBLIC_*`-Variablen |

## Profile und Dateien

| Profil            | Typische Datei    | `validate_env_profile.py --profile` |
| ----------------- | ----------------- | ----------------------------------- |
| Lokal / Paper     | `.env.local`      | `local`                             |
| Shadow / Pre-Prod | `.env.shadow`     | `shadow`                            |
| Production        | `.env.production` | `production`                        |

`staging` als CLI-Profil existiert für die Matrix-Spalte „staging“ (gleiche Keys wie Shadow); für Dateien nutzt du **`shadow`**.

## Pflichtvariablen (Kurzüberblick)

Aus der Matrix u. a.:

- **Datenhaltung:** `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_DOCKER`, `REDIS_URL`, `REDIS_URL_DOCKER`
- **Kern-Secrets:** `JWT_SECRET`, `SECRET_KEY`, `ADMIN_TOKEN`, `ENCRYPTION_KEY`, `INTERNAL_API_KEY`
- **Gateway / Dashboard:** `GATEWAY_JWT_SECRET`, `API_GATEWAY_URL`, `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_BASE_URL`
- **Shadow/Production zusätzlich:** `DASHBOARD_GATEWAY_AUTHORIZATION` (Bearer-JWT mit `gateway:read`)

**Lokal** ist `DASHBOARD_GATEWAY_AUTHORIZATION` in der Matrix _optional_, bis das JWT geschrieben wurde. Deshalb:

1. Erster Lauf: `validate_env_profile.py --profile local` (ohne Operator-Token)
2. `scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`
3. Zweiter Lauf: `validate_env_profile.py --profile local --with-dashboard-operator`

`pnpm dev:up` und `bootstrap_stack` machen das automatisch.

## Bedingte Regeln (validate_env_profile)

- **`PRODUCTION=true`** oder Profil **shadow/production**: `LLM_USE_FAKE_PROVIDER` muss **false** sein, **`OPENAI_API_KEY`** gesetzt.
- **Lokal** mit `LLM_USE_FAKE_PROVIDER=false`: **`OPENAI_API_KEY`** Pflicht.
- **`COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE=true`**: **`TELEGRAM_BOT_TOKEN`** Pflicht.
- **`LIVE_TRADE_ENABLE=true`** ohne **`BITGET_DEMO_ENABLED`**: Bitget-API-Zugangsdaten Pflicht.

## NPM-Skripte (Repo-Root)

```bash
pnpm config:validate              # .env.local, vor Mint
pnpm config:validate:operator     # .env.local, inkl. DASHBOARD_GATEWAY_AUTHORIZATION
pnpm config:validate:shadow       # .env.shadow
pnpm config:validate:production   # .env.production
```

Voraussetzung: `python` im PATH und Projekt-Root als Arbeitsverzeichnis.

## Next.js Dashboard: strikte ENV lokal testen

Standard: Runtime-Gate nur bei **`NODE_ENV=production`** (`next build` / `next start`).

Für **dieselben Checks in Development**:

```bash
DASHBOARD_ENFORCE_ENV=true pnpm dev
```

## Veraltete / unsichere Defaults

- Kein Verlass auf „stilles“ `localhost` ohne gesetzte URLs in Production: Matrix verlangt explizite **`API_GATEWAY_URL`** und **`NEXT_PUBLIC_*`**.
- Direkte Browser-Aufrufe des Gateways mit Secrets sind durch das Dashboard-Design unüblich; siehe BFF unter `/api/dashboard/gateway/`.

## Bei Fehlern

1. Meldung der CLI oder des Dashboard-Starts lesen (Variablenname steht in der Ausgabe).
2. **`docs/LOCAL_START_MINIMUM.md`** für den schnellen lokalen Pfad.
3. Matrix und Semantik: **`docs/env_profiles.md`**, **`docs/SECRETS_MATRIX.md`**.
