## Repo Truth Matrix

Stand: 2026-03-30

Zweck: kanonischer, eingefrorener Ausgangsbefund fuer alle Folgeaenderungen im Monorepo. Dieses Dokument beschreibt den aktuellen Ist-Zustand des Repos, benennt dokumentierte Abkuerzungen, offene Drift und echte Produktionsblocker. Es ersetzt keine Runbooks, ist aber die aktuelle Quelle der Wahrheit fuer Inventur und Freeze.

**Zielarchitektur fuer Folgeaenderungen:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

### Kanonische Quellen

1. `docker-compose.yml`
2. `infra/service-manifest.yaml`
3. `config/settings.py` und service-spezifische `config.py` / `app.py`
4. `.env*.example`
5. `.github/workflows/ci.yml`
6. `tests/`, `shared/python/tests/`

Wenn Doku und Code widersprechen, gilt in diesem Freeze der Laufzeitstand aus Code, Compose und ENV-Validatoren.

### Repo-Inventar

| Bereich                                | Ist-Zustand                                                       | Evidenz                                                                                                                                                                                                                           |
| -------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| App-Frontend                           | 1 produktive Next.js-App                                          | `apps/dashboard/`                                                                                                                                                                                                                 |
| Python-Services                        | 13 Services                                                       | `services/*/pyproject.toml`                                                                                                                                                                                                       |
| Shared Runtime                         | Python + TS vorhanden                                             | `shared/python/`, `shared/ts/`                                                                                                                                                                                                    |
| Instrumentenkatalog / Metadatenservice | zentraler Snapshot + Resolver + Preflight-/Health-Layer vorhanden | `shared/python/src/shared_py/bitget/catalog.py`, `shared/python/src/shared_py/bitget/metadata.py`, `infra/migrations/postgres/460_instrument_catalog.sql`, `infra/migrations/postgres/470_instrument_catalog_metadata_fields.sql` |
| Vertrage                               | JSON-Schemas, Event-Katalog, OpenAPI vorhanden                    | `shared/contracts/`                                                                                                                                                                                                               |
| Migrationen                            | 65 Postgres-Migrationen                                           | `infra/migrations/postgres/*.sql`                                                                                                                                                                                                 |
| Doku                                   | >90 Markdown-Dokumente                                            | `docs/*.md`                                                                                                                                                                                                                       |
| CI                                     | 1 zentrale GitHub-Workflow-Pipeline                               | `.github/workflows/ci.yml`                                                                                                                                                                                                        |
| Compose                                | 1 Basis-Stack + 1 lokales Publish-Overlay                         | `docker-compose.yml`, `docker-compose.local-publish.yml`                                                                                                                                                                          |

### Runtime-Topologie

| Komponente         | Vorhanden | In Compose             | Primäre Rolle                        | Befund                                                                                                           |
| ------------------ | --------- | ---------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `postgres`         | ja        | ja                     | Persistenz                           | intern im Compose-Netz                                                                                           |
| `redis`            | ja        | ja                     | Eventbus / Cache / Rate-Limits       | intern im Compose-Netz                                                                                           |
| `market-stream`    | ja        | ja                     | Bitget-Marktdaten                    | family-aware umgestellt, aber weiter single-process je Instrument-Config                                         |
| `feature-engine`   | ja        | ja                     | Feature-Berechnung                   | vorhanden                                                                                                        |
| `structure-engine` | ja        | ja                     | Marktstruktur                        | vorhanden                                                                                                        |
| `drawing-engine`   | ja        | ja                     | Drawings / Zonen                     | vorhanden                                                                                                        |
| `signal-engine`    | ja        | ja                     | deterministischer Kern               | vorhanden, mit Spezialisten-Router-Trace                                                                         |
| `news-engine`      | ja        | ja                     | News-Ingest / Scoring                | vorhanden, LLM nur Hilfspfad                                                                                     |
| `llm-orchestrator` | ja        | ja                     | strukturierte LLM-Ausgaben           | vorhanden, direkt intern gehärtet                                                                                |
| `paper-broker`     | ja        | ja                     | Paper / Referenz-Ausfuehrung         | vorhanden; bei `live`-Contract in shadow/prod **kein** stilles Fixture-Fallback (Fetch-Fehler -> `RuntimeError`) |
| `learning-engine`  | ja        | ja                     | Registry / Backtest / Drift          | vorhanden                                                                                                        |
| `live-broker`      | ja        | ja                     | Control-Plane / Exchange-Ausfuehrung | vorhanden, family-aware Basis vorhanden                                                                          |
| `alert-engine`     | ja        | ja                     | Telegram / Outbox / Alerts           | vorhanden, Webhook jetzt realer Ingress                                                                          |
| `monitor-engine`   | ja        | ja                     | Monitoring / Gauges / Alerts         | vorhanden                                                                                                        |
| `api-gateway`      | ja        | ja                     | Edge / Aggregation / Auth            | vorhanden                                                                                                        |
| `dashboard`        | ja        | ja                     | Operator-UI                          | vorhanden                                                                                                        |
| `prometheus`       | ja        | Profil `observability` | Metrics                              | optional, nicht Basis-Stack                                                                                      |
| `grafana`          | ja        | Profil `observability` | Dashboards                           | optional, Dashboards im Repo weitgehend Platzhalter                                                              |

### Fehlende oder nur teilweise realisierte Bereiche

| Bereich                                                          | Status             | Schwere  | Evidenz                                                                                                                  |
| ---------------------------------------------------------------- | ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Family-weite Multi-Instrument-Orchestrierung                     | teilweise          | major    | zentraler Katalog und Metadatenservice vorhanden, aber Runtime weiter ueberwiegend single-instrument pro Serviceinstanz  | `services/market-stream/src/market_stream/app.py`, `shared/python/src/shared_py/bitget/catalog.py`, `shared/python/src/shared_py/bitget/metadata.py` |
| Vollstaendig replay-stabile Event-Metadaten                      | nein               | major    | `shared/python/src/shared_py/eventbus/envelope.py`                                                                       |
| Family-neutrale Registry-/Scope-Modellierung ohne BTC-Defaults   | teilweise          | major    | `services/learning-engine/src/learning_engine/registry/models.py`, `infra/migrations/postgres/150_strategy_registry.sql` |
| Stilles Fixture-Fallback bei Live-Contract in prod-like Umgebung | nein (unterbunden) | erledigt | `contract_config.py`, `tests/paper_broker/test_contract_config_family_matrix.py`                                         |
| Vollstaendige Dashboard-/Gateway-Contract-Abdeckung              | teilweise          | medium   | `shared/contracts/openapi/api-gateway.openapi.json`, `shared/ts/`                                                        |
| Ausgefuellte Grafana-Dashboards                                  | nein               | medium   | `infra/observability/grafana/dashboards.json`                                                                            |

### Demo-, Fake-, Fixture- und Dev-Abkuerzungen

| Mechanismus                               | Ist-Zustand                                                                             | Produktionsschutz             | Befund                                  |
| ----------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------- | --------------------------------------- |
| `BITGET_DEMO_ENABLED`                     | vorhanden                                                                               | in `PRODUCTION=true` verboten | sauber fuer Dev/Test, kein Prod-Default |
| `LLM_USE_FAKE_PROVIDER`                   | vorhanden                                                                               | in Shadow/Prod verboten       | akzeptabel als Testpfad                 |
| `NEWS_FIXTURE_MODE`                       | vorhanden                                                                               | in Shadow/Prod verboten       | akzeptabel als Testpfad                 |
| `PAPER_SIM_MODE`                          | vorhanden                                                                               | in Produktion verboten        | akzeptabel fuer Paper/Test              |
| Contract-Fixture-Fallback im Paper-Broker | nur bei `fixture`-Mode oder lokaler Nicht-Prod; **live** in shadow/prod **fail-closed** | prod-like geschuetzt          | siehe `_fixture_fallback_allowed`       |
| `docker-compose.local-publish.yml`        | vorhanden                                                                               | bewusst lokales Overlay       | okay, aber nur lokal/CI                 |

### Betriebsmodi

| Modus         | Tatsächlicher Gate-Stand                       | Befund                                            |
| ------------- | ---------------------------------------------- | ------------------------------------------------- |
| `paper`       | kein echter Order-Submit                       | stabiler Referenzpfad                             |
| `shadow`      | gleiche Entscheidungslogik, kein Live-Submit   | stabiler produktionsnaher Modus                   |
| `live`        | operator-gated ueber ENV + Broker-Gates + Risk | vorhanden                                         |
| Telegram-Chat | read-only/mute/status + admin-replay           | keine Strategieparameter-Mutation im Standardpfad |
| LLM           | strukturierte Hilfskomponente                  | kein LLM-only-Trading                             |

### Sicherheitsoberflaechen

| Oberflaeche                         | Ist-Zustand                                                                | Schwere    | Evidenz                                                                                                       |
| ----------------------------------- | -------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------- |
| Gateway sensible Routen             | JWT/Internal-Key, Audit, Rate-Limits                                       | medium     | `services/api-gateway/src/api_gateway/auth.py`                                                                |
| Direkter `llm-orchestrator`-Zugriff | interner Service-Key moeglich und in Prod erforderlich                     | verbessert | `shared/python/src/shared_py/service_auth.py`, `services/llm-orchestrator/src/llm_orchestrator/api/routes.py` |
| Direkter `live-broker`-Ops-Zugriff  | interner Service-Key moeglich und in Prod erforderlich                     | verbessert | `services/live-broker/src/live_broker/api/routes_ops.py`                                                      |
| `alert-engine` Admin/Replay         | `X-Admin-Token` + optional interner Key, Replay in Shadow/Prod default aus | verbessert | `services/alert-engine/src/alert_engine/api/routes_admin.py`                                                  |
| Telegram Webhook                    | jetzt implementiert mit Secret-Header                                      | verbessert | `services/alert-engine/src/alert_engine/api/routes_webhook.py`                                                |
| Replay-/Debug-Routen                | nicht repo-weit konsistent deaktiviert/auditiert                           | medium     | `SECURITY_ALLOW_*`-Schalter in `config/settings.py`, einzelne Service-Routen                                  |

### BTCUSDT- und USDT-FUTURES-Lastigkeit

BTCUSDT- und USDT-FUTURES-Annahmen sind **historisch** und in Beispielen/Fixtures weiterhin sichtbar. Der produktionsrelevante Kern wurde im aktuellen Workspace deutlich reduziert, ist aber noch nicht repo-weit vollstaendig neutralisiert.

| Kategorie                 | Hauptblocker                                                                                                                                                                        | Evidenz                                                                                                                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Config / ENV              | explizite Startkohorten / Beispielprofile und capability-basierte Family-Defaults gemischt; Shadow/Prod-Profile brauchen weiter echte account-spezifische Universe-/Watchlist-Werte | `config/settings.py`, `.env*.example`, `shared/python/src/shared_py/bitget/config.py`                                                                                                             |
| Event-Huelle              | Replay-Trace: stabile `event_id`/`ingest_ts_ms` via Validator + `replay_determinism`; ohne Replay-Trace weiterhin UUID/Wall-Clock                                                   | `shared/python/src/shared_py/eventbus/envelope.py`, `shared/python/src/shared_py/replay_determinism.py`                                                                                           |
| Registry / Scope          | kanonischer Scope eingefuehrt; historische Migrationen und Beispielpfade bleiben nachzupruefen                                                                                      | `services/learning-engine/src/learning_engine/registry/models.py`, `infra/migrations/postgres/150_strategy_registry.sql`, `infra/migrations/postgres/591_strategy_scope_canonical_instrument.sql` |
| Paper-Broker              | per-Symbol-Fixtures (`contract_config_ethusdt.json` etc.) + Legacy-Fallback `contract_config_btcusdt.json`                                                                          | `services/paper-broker/src/paper_broker/engine/contract_config.py`, `services/paper-broker/fixtures/`                                                                                             |
| Gateway / Dashboard       | Default-Symbol wird jetzt aus Watchlist/Universe abgeleitet; Restlastigkeit liegt primär in Beispielen und expliziten Startkohorten                                                 | `config/gateway_settings.py`, `apps/dashboard/src/lib/env.ts`, `services/api-gateway/src/api_gateway/routes_live.py`                                                                              |
| News / LLM / Docs / Tests | BTCUSDT in Topics, Fixtures, Tests, Runbooks                                                                                                                                        | `services/news-engine/`, `services/llm-orchestrator/`, `tests/`, `docs/`                                                                                                                          |

Bewertung: der Repo-Kern ist nicht mehr rein futures-only und produktionsrelevante BTCUSDT-/USDT-FUTURES-Defaults wurden reduziert (u. a. Multi-Symbol-Discovery in `.env.production.example`, ETH-Paper-Fixture). Verbleibende Lastigkeit: Tests/Runbooks mit explizitem BTCUSDT, Legacy-Fallback-Datei im Paper-Broker, historische ENV-Namen wie `STRAT_BASE_QTY_BTC`.

### Build-, CI-, Compose- und ENV-Drift

| Thema                       | Befund                                                                                                 | Schwere  | Evidenz                                                |
| --------------------------- | ------------------------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------ |
| README-Startreihenfolge     | war vertauscht, jetzt korrigiert                                                                       | behoben  | `README.md`                                            |
| `SYSTEM_AUDIT_MASTER.md`    | **bereinigt 2026-03-30:** nur Verweis auf Truth-/Gap-Matrizen                                          | erledigt | `docs/SYSTEM_AUDIT_MASTER.md`                          |
| `REPO_FREEZE_GAP_MATRIX.md` | historischer Backlog, nicht aktueller Vollstand                                                        | major    | `docs/REPO_FREEZE_GAP_MATRIX.md`                       |
| `.env.production.example`   | stark auf externe Hosts / K8s-artige Namen ausgerichtet                                                | medium   | `.env.production.example`, `docs/Deploy.md`            |
| Python Runtime-Deps         | **Images/CI:** `constraints-runtime.txt`; Services nutzen ranges in `pyproject.toml` fuer editable Dev | medium   | `constraints-runtime.txt`, `services/*/pyproject.toml` |
| CI Security-Audits          | nicht blockierend                                                                                      | medium   | `.github/workflows/ci.yml`                             |
| Coverage-Gates              | teilweise ueber Zusatztool statt global fail-under                                                     | medium   | `.coveragerc`, `tools/check_coverage_gates.py`         |

### Test- und Qualitaetswahrheit

| Bereich      | Ist-Zustand                     | Befund                                                           |
| ------------ | ------------------------------- | ---------------------------------------------------------------- |
| Python-Tests | breit vorhanden                 | gute Kernabdeckung, aber nicht gleichmaessig ueber alle Services |
| Shared-Tests | vorhanden                       | decken Event-/Bitget-/Exit-Grundlagen ab                         |
| Dashboard    | Jest + Shell-Smokes             | teilweise getrennte Gate-Wege                                    |
| Coverage     | Service-spezifische Zusatzgates | kein globaler repo-weiter Fail-Under fuer alle Services          |

### Artefaktmuell und Platzhalter

| Artefakt                                                                                                      | Befund                                                                     | Schwere |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------- |
| `infra/observability/grafana/dashboards.json`                                                                 | leerer Platzhalter                                                         | medium  |
| diverse Fixtures unter `tests/fixtures/`, `services/news-engine/fixtures/`, `services/paper-broker/fixtures/` | legitim fuer Tests, aber prod-nahes Contract-Fallback bleibt problematisch | medium  |
| lokale Cache-Verzeichnisse                                                                                    | nicht kanonisch, sofern im VCS                                             | minor   |

### Freeze-Erklaerung

Dieser Stand ist bewusst eingefroren. Alle Folgeaenderungen muessen gegen diese Matrix und die aktuelle Gap-Matrix in `docs/REPO_FREEZE_GAP_MATRIX.md` begruendet werden. Solange kritische oder major Luecken offen sind, ist der Gesamtzustand nicht als institutionell freigegeben zu markieren.
