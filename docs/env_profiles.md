# ENV-Profile und Secret-Strategie

**Validierung & Fail-fast:** siehe **[CONFIGURATION.md](CONFIGURATION.md)** (CLI, Skripte, Next-`instrumentation`).

## Welche Datei wofuer?

| Profil                | Vorlage                                                     | Zweck                                                                                                                                                   |
| --------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lokal / Paper-Dev** | `.env.local.example` → `.env.local`                         | `PRODUCTION=false`, `APP_ENV=local`, `EXECUTION_MODE=paper`. Demo/Fixture/Fake-Provider **erlaubt**.                                                    |
| **Shadow**            | `.env.shadow.example` → `.env.shadow`                       | `PRODUCTION=true`, `APP_ENV=shadow`, `EXECUTION_MODE=shadow`. Produktionshärtung, echte Infrastruktur, **keine** Demo-/Test-Pfade, Burn-in-Gates aktiv. |
| **Production**        | `.env.production.example` → `.env.production` / Host-`.env` | `PRODUCTION=true`, `APP_ENV=production`. Starttypisch `EXECUTION_MODE=shadow` bis Live-Freigabe; danach nur operator-gated Mirror-Ramp.                 |
| **Tests / CI**        | `.env.test.example` → `.env.test`                           | Determinismus, Fixtures, kurze Timeouts. Nicht fuer Shadow/Prod-Deploy.                                                                                 |
| **Katalog**           | `.env.example`                                              | Vollständige Key-Liste und Semantik — **nicht** ungefiltert als Laufzeit-ENV kopieren.                                                                  |

**Dashboard ↔ API-Gateway:** `FRONTEND_URL` (Browser-Origin) muss in `CORS_ALLOW_ORIGINS` vorkommen; `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_BASE_URL` müssen dieselbe öffentliche Gateway-Basis wie `APP_BASE_URL` verwenden (`http`+`ws` oder `https`+`wss`). Kurzkommentar und Regeln im Kopf von `.env.local.example`; Details `docs/operator_urls_and_secrets.md`.

`config/settings.BaseServiceSettings` validiert bei `PRODUCTION=true` u. a.: keine Debug-Routen, keine Demo/Fixture/Fake-News/Fake-LLM, kein Paper-Sim, `VAULT_MODE` in `hashicorp|aws`, keine `localhost`-URLs in ausgewählten öffentlichen URLs, und keine Werte, die wie Platzhalter aussehen (`<SET_ME>`, `changeme`, Teilstrings `example.com` / `example.internal`, …).

Zusaetzlich prueft `validate_required_secrets` beim Service-Start die Pflicht-ENV aus `config/required_secrets_matrix.json` (pro Service und `PRODUCTION`); siehe `docs/SECRETS_MATRIX.md`.

## Wie Profile wirklich geladen werden

Die Python-Services nutzen jetzt dieselbe Profilauflösung:

1. `CONFIG_ENV_FILE`
2. `COMPOSE_ENV_FILE`
3. `ENV_PROFILE_FILE`
4. `STACK_PROFILE` oder `APP_ENV` (`local`, `shadow`, `production`, `test`)
5. Fallback `.env.local`

Damit gilt:

- lokal ohne weitere Angabe: `.env.local`
- Compose/Wrapper mit `COMPOSE_ENV_FILE=.env.shadow`: Shadow-Profil
- Tests mit `APP_ENV=test` oder `.env.test`: gleiche Kernlogik, andere Gates

**Compose-Container:** `docker-compose.yml` setzt `CONFIG_ENV_FILE` aus `COMPOSE_ENV_FILE` (Default `.env.local`), damit dieselbe Profilwahl wie auf dem Host auch in den App-Containern in `resolve_standard_env_files()` ankommt — zusaetzlich zu den bereits injizierten Variablen aus `env_file:`.

Es gibt keine fachlich andere Shadow- oder Production-Logik; nur Security-, Secret-, Demo-/Fixture- und Ausfuehrungsgates unterscheiden sich.

## Zentrale Flags (Vertrag)

- **`PRODUCTION`**: `true` = Profil **Shadow** oder **Production** (harte Validierung, Secret-Pflichtfelder, Vault-Pflicht). Unabhängig davon, ob noch Paper-Pfade im Code existieren — bei `true` sind Demo-Pfade gesperrt.
- **`APP_ENV`**: `local` | `shadow` | `production` | `test` — benennt die Umgebung; bei `PRODUCTION=true` nur `shadow` oder `production`.
- **`EXECUTION_MODE`**: `paper` | `shadow` | `live` — **Trading-Laufzeitpfad**.
- **`SHADOW_TRADE_ENABLE`**: nur `true`, wenn `EXECUTION_MODE=shadow` (Shadow-Handelspfad / Live-Broker-Beobachtung ohne Order-Submit, je nach Service).
- **`LIVE_TRADE_ENABLE`**: nur `true`, wenn `EXECUTION_MODE=live` **und** `LIVE_BROKER_ENABLED=true`.
- **`BITGET_DEMO_ENABLED`**: nur in **local** / **test**; bei `PRODUCTION=true` verboten.
- **`BITGET_MARKET_FAMILY` / `BITGET_PRODUCT_TYPE` / `BITGET_MARGIN_ACCOUNT_MODE`**: definieren den family-aware Instrumentkontext. Nicht die Fantasie eines Operators, sondern nur in Kombination mit realer Discovery-/Metadata-Evidenz als produktive Family verwenden.
- **`BITGET_UNIVERSE_MARKET_FAMILIES`**: zulässige Familien im Stack, aktuell mindestens `spot,margin,futures`.
- **`BITGET_FUTURES_ALLOWED_PRODUCT_TYPES`**: erlaubte Futures-Produkttypen fuer den Stack.
- **`BITGET_UNIVERSE_SYMBOLS`**: kanonische Kandidatenliste fuer das beobachtete Universum; kann leer bleiben, wenn Discovery nur account-/metadata-getrieben laufen soll.
- **`BITGET_WATCHLIST_SYMBOLS`**: Operator-/UI-nahe Untermenge des Universums.
- **`FEATURE_SCOPE_SYMBOLS` / `FEATURE_SCOPE_TIMEFRAMES`**: aktiver Feature-/Analytics-Scope.
- **`SIGNAL_SCOPE_SYMBOLS`**: Symbolscope fuer Signalerzeugung; wenn leer, erbt er aus dem Feature-Scope.
- **`STRUCTURED_MARKET_CONTEXT_ENABLED` / `SMC_*`**: deterministischer Kontextlayer (Facetten, Decay, Surprise, Soft/Hard/Live-Impacts) in der Signal-Engine; Semantik und Audit-Pfade in `docs/structured_market_context.md`.
- **`BITGET_SPOT_DEFAULT_QUOTE_COIN` / `BITGET_MARGIN_DEFAULT_QUOTE_COIN` / `BITGET_MARGIN_DEFAULT_ACCOUNT_MODE` / `BITGET_MARGIN_DEFAULT_LOAN_TYPE` / `BITGET_FUTURES_DEFAULT_PRODUCT_TYPE` / `BITGET_FUTURES_DEFAULT_MARGIN_COIN`**: family-spezifische Defaults fuer Resolver, UI und Runbooks.
- **`INSTRUMENT_CATALOG_REFRESH_INTERVAL_SEC` / `INSTRUMENT_CATALOG_CACHE_TTL_SEC` / `INSTRUMENT_CATALOG_MAX_STALE_SEC`**: steuern Refresh-, Cache- und Stale-Grenzen des zentralen Instrumentenkatalogs.
- **`LIVE_ALLOWED_MARKET_FAMILIES` / `LIVE_ALLOWED_SYMBOLS` / `LIVE_ALLOWED_PRODUCT_TYPES`**: harte Live-Allowlisten oberhalb des globalen Universums.
- **`LIVE_REQUIRE_EXECUTION_BINDING`**: Opening-Orders nur mit gueltiger `execution_id`-Bindung aus dem Live-Broker-Journal.
- **`LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN`**: echte Opening-Orders nur nach explizitem Operator-Release.
- **`REQUIRE_SHADOW_MATCH_BEFORE_LIVE`**: Live-Kandidaten fallen auf `blocked`, wenn der Shadow-/Live-Abgleich nicht passt.
- **`RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE`**: konservativer Live-Ramp-Cap oberhalb des generellen Max-Hebels; Startstufe bleibt 7.
- **`RISK_ELEVATED_LEVERAGE_LIVE_ACK`**: bei **`PRODUCTION=true`** und **`LIVE_TRADE_ENABLE=true`**: wenn **`RISK_ALLOWED_LEVERAGE_MAX` > 7**, muss **`true`** sein — trennt Schema-Obergrenze (7..75) vom operativen Erst-Burn-in (MAX=7); siehe `docs/LaunchChecklist.md`.
- **`NEWS_FIXTURE_MODE`**: nur **local** / **test**; bei `PRODUCTION=true` verboten.
- **`LLM_USE_FAKE_PROVIDER`**: nur **local** / **test**; bei `PRODUCTION=true` verboten.
- **`PAPER_SIM_MODE` / `PAPER_CONTRACT_CONFIG_MODE`**: In Produktion muss `PAPER_CONTRACT_CONFIG_MODE=live` und `PAPER_SIM_MODE=false` sein.
- **`TELEGRAM_DRY_RUN`**: nur **local** / **test**; bei `PRODUCTION=true` verboten.

Ableitbare Konvention (kein Ersatz fuer Operator-Secrets): Stream-Namen, interne Service-Ports und Health-Pfade können aus dem Repo übernommen werden, solange sie zur tatsächlichen Topologie passen.

## Operator-Pflicht (ohne Defaults aus dem Repo)

Mindestens bei **Shadow** und **Production** (alles, was `PRODUCTION=true` lädt):

1. **Identität / Crypto**: `ADMIN_TOKEN`, `SECRET_KEY`, `JWT_SECRET`, `ENCRYPTION_KEY` — starke Zufallswerte, nur Secret-Store oder sichere ENV-Injektion.
2. **Gateway**: `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY`; bei erzwungenem sensiblen Auth (Standard in Shadow/Prod) mindestens eines davon.
3. **Daten**: `DATABASE_URL`, `REDIS_URL` (und Docker-Varianten, falls genutzt) mit echten Credentials; `POSTGRES_PASSWORD` etc.
4. **Vault**: `VAULT_ADDR` + `VAULT_TOKEN` **oder** `VAULT_ROLE_ID` + `VAULT_SECRET_ID`; bei AWS-KMS-Pfad `KMS_KEY_ID`.
5. **Öffentliche URLs**: `APP_BASE_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`, `NEXT_PUBLIC_*` (Dashboard-Build) — siehe **`docs/operator_urls_and_secrets.md`**. Ohne `localhost`, ohne Platzhalter-Substrings aus `_PLACEHOLDER_MARKERS` in `config/settings.py`.
6. **TLS am Edge**: bei `APP_BASE_URL` mit `https://` muss `GATEWAY_SEND_HSTS=true` und kein `GATEWAY_SSE_COOKIE_SECURE=false` gesetzt sein (Gateway-Validierung).
7. **Bitget (echtes Konto)**: `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` — wenn private Marktdaten / Handelspfad aktiv ist.
8. **Inventar / Discovery**: `BITGET_DISCOVERY_SYMBOLS` dient nur als Seed-/Kandidatenliste fuer Discovery und ersetzt keine reale Bitget-Metadatenlage. In `.env.production.example` ist ein **Multi-Symbol-Seed** (z. B. BTCUSDT,ETHUSDT) vorgesehen; Kanon bleiben `BITGET_UNIVERSE_SYMBOLS` / Watchlist nach echter Discovery.
9. **Dashboard-BFF**: `DASHBOARD_GATEWAY_AUTHORIZATION` (vollständiger `Authorization`-Header) ist bei **Shadow/Production** laut `config/required_secrets_matrix.json` **Pflicht**; lokal Matrix-`optional`, bis JWT gemint (`scripts/mint_dashboard_gateway_jwt.py`) — CLI mit `--with-dashboard-operator` prüfen.
10. **Optional je Betrieb**: News-API-Keys, LLM-Provider-Keys (siehe bedingte Regeln in `tools/validate_env_profile.py`), Telegram-Tokens/Webhook-Secrets, Grafana-Admin-Passwort.

## Konfigurationsmatrix

| Bereich               | Universum / Scope                                                                                                                                               | local                    | test                                 | shadow                       | production                            |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------ | ---------------------------- | ------------------------------------- |
| Marktuniversum        | `BITGET_UNIVERSE_MARKET_FAMILIES`, `BITGET_UNIVERSE_SYMBOLS`, `BITGET_WATCHLIST_SYMBOLS`                                                                        | frei / dev-orientiert    | deterministisch / fixture-freundlich | real / konservativ           | real / konservativ                    |
| Family-Defaults       | `BITGET_*_DEFAULT_*`                                                                                                                                            | erlaubt                  | erlaubt                              | verpflichtend konsistent     | verpflichtend konsistent              |
| Feature-/Signal-Scope | `FEATURE_SCOPE_*`, `SIGNAL_SCOPE_SYMBOLS`                                                                                                                       | flexibel                 | stabil fuer Tests                    | produktionsnah               | produktionsnah                        |
| Instrumentenkatalog   | `INSTRUMENT_CATALOG_*`                                                                                                                                          | kurze Intervalle erlaubt | kurze Intervalle / kleine TTL        | reale Refresh-/Stale-Grenzen | reale Refresh-/Stale-Grenzen          |
| Live-Allowlisten      | `LIVE_ALLOWED_*`                                                                                                                                                | oft eng oder deaktiviert | eng / testnah                        | eng und explizit             | eng und explizit                      |
| Live-Mirror-Gates     | `LIVE_REQUIRE_EXECUTION_BINDING`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE`                                             | aus                      | optional                             | aktiv                        | aktiv                                 |
| Demo/Fake/Fixture     | `BITGET_DEMO_ENABLED`, `NEWS_FIXTURE_MODE`, `LLM_USE_FAKE_PROVIDER`, `PAPER_SIM_MODE`, `BITGET_ALLOW_DEMO_SCHEMA_SEEDS` (nur local, SQL unter `postgres_demo/`) | erlaubt                  | erlaubt                              | verboten                     | verboten                              |
| Live-Ausfuehrung      | `EXECUTION_MODE`, `LIVE_TRADE_ENABLE`, `STRATEGY_EXEC_MODE`                                                                                                     | paper                    | paper                                | shadow                       | shadow als Default, live nur explizit |

Demo-Bitget-Keys (`BITGET_DEMO_*`) sind **nur** nötig, wenn `BITGET_DEMO_ENABLED=true` (ausschließlich local/test).

## Harte Verbote (Shadow / Production)

Siehe Validierung in `config/settings.py` (`_prod_safety`): u. a. `DEBUG=true`, `API_AUTH_MODE=none`, `SECURITY_ALLOW_*_DEBUG_ROUTES`, `BITGET_DEMO_ENABLED`, `NEWS_FIXTURE_MODE`, `LLM_USE_FAKE_PROVIDER`, `PAPER_SIM_MODE`, `PAPER_CONTRACT_CONFIG_MODE!=live`, `TELEGRAM_DRY_RUN`, `VAULT_MODE=false`, fehlende Vault-Credentials.

## Migration bestehender lokaler Setups

1. Entfernen fester Dev-Tokens wie `ADMIN_TOKEN=local-admin-token` — durch starke lokale Werte oder JWT-basierten Gateway-Zugang ersetzen.
2. Shadow/Prod: Gateway-Block aus `.env.production.example` / `.env.shadow.example` übernehmen (`GATEWAY_ENFORCE_SENSITIVE_AUTH`, `GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=false`).
3. Leere `BITGET_DEMO_*`-Zeilen in Shadow/Prod entfernen — nicht nötig, wenn `BITGET_DEMO_ENABLED=false` (Defaults greifen im Code).
4. URLs mit `example.com` / `example.internal` durch echte interne Hosts ersetzen, sonst schlägt die Produktions-Validierung fehl.

Weitere Deploy-Details: `docs/Deploy.md`, `docs/LaunchChecklist.md`.
