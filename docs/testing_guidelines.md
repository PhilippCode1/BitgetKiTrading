# Teststrategie & Qualitaet

Betriebliche **Go-Live-Reihenfolge** (Secrets, Migrationen, Healthchecks, Shadow, Live): **`docs/LaunchChecklist.md`**.

## Ziele

- **Unit-Tests**: schnelle, deterministische Pruefung von Kernlogik (Features, Scoring, Risiko, Shared-Libs, Monitor-Metriken, Live-Broker-Exchange-Client).
- **Integrationstests**: DB/Redis mit `TEST_DATABASE_URL` / `TEST_REDIS_URL` und Marker `integration`; HTTP-Stack-Tests **skippen**, solange `API_GATEWAY_URL` / JWT nicht gesetzt sind (kein Fake-Prod).
- **Schema-Tests**: API- und Fixture-JSON gegen Schemas unter `infra/tests/schemas/` (`tools/check_schema.py`).
- **Coverage**:
  - **shared_py**: mindestens **80 %** kombiniert (Statements + Branches), geprueft durch `coverage report --include=**/shared_py/** --fail-under=80`.
  - **Kritische Pfade** (Risk/Exit/Gating/Signal/Live-Execution/Exchange-Client): mindestens **90 % Zeilen-Deckung** aggregiert ueber die in `tools/check_coverage_gates.py` gelisteten Dateien (`live_broker/orders/*` ist bewusst **nicht** in diesem Gate; dort greifen die bestehenden Unit-Tests unter `tests/unit/live_broker/`).
  - **Hinweis**: `coverage.py` laedt `.coveragerc` (gleiche `source`-Liste wie `pyproject.toml`); ohne aktualisierte `.coveragerc` fehlen Pakete wie `live-broker` in der Messung.

## Lokale Entwicklung vs. CI

| Bereich               | CI                                                                                                                        | Lokal                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Unit + `live_mock`    | `coverage run -m pytest tests shared/python/tests -m "not integration"`                                                   | gleich                                                                                            |
| Coverage-Gates        | `python tools/check_coverage_gates.py` (nach `coverage run`)                                                              | gleich                                                                                            |
| DB-Migrationen        | `python infra/migrate.py` mit Service-Postgres (`DATABASE_URL`)                                                           | Postgres starten, `DATABASE_URL` setzen                                                           |
| DB/Redis-Integration  | Job `python`: Postgres+Redis-Service, `pytest … -m integration`                                                           | `docker compose -f infra/tests/docker-compose.test.yml` + `TEST_*_URL`                            |
| Stack-HTTP            | Nur wenn URLs + JWT gesetzt                                                                                               | Stack starten, URLs exportieren                                                                   |
| Compose + Healthcheck | Job `compose_healthcheck`: `.env.local` aus Example, `docker compose up -d --build`, `scripts/healthcheck.sh` mit Retries | `COMPOSE_ENV_FILE=.env.local docker compose up -d` + alle `*_URL` wie in `scripts/healthcheck.sh` |

**Live-Mock:** Contract-Objekte unter `tests/integration/doubles/bitget_rest_contract.py` — keine echten Bitget-Hosts.

**Stack-HTTP:** `INTEGRATION_GATEWAY_JWT_SECRET` muss dem Gateway `GATEWAY_JWT_SECRET` entsprechen. Live-Broker: `INTEGRATION_LIVE_BROKER_URL` oder `LIVE_BROKER_URL`.

## Verzeichnisse

| Pfad                                              | Inhalt                                                |
| ------------------------------------------------- | ----------------------------------------------------- |
| `tests/unit/<komponente>/`                        | Unit-Tests pro Engine/Service                         |
| `tests/fixtures/deterministic_signal_payloads.py` | Python-Builder neben JSON-Fixtures                    |
| `tests/integration/`                              | HTTP-Stack, DB/Redis, Compose-Smoke, Contract-Doubles |
| `tools/check_coverage_gates.py`                   | Shared-Py- und kritische Modul-Schwellen              |
| `.github/workflows/ci.yml`                        | Jobs: `python`, `dashboard`, `compose_healthcheck`    |

## Ausfuehrung (lokal)

```bash
pip install -r requirements-dev.txt
pip install -e ./shared/python
# weitere -e installs wie in `.github/workflows/ci.yml`
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ci_dummy
export REDIS_URL=redis://localhost:6379/0
python infra/migrate.py
coverage run -m pytest tests shared/python/tests -m "not integration"
python tools/check_coverage_gates.py
pytest tests/integration tests/learning_engine -m integration
```

**Dashboard (wie CI, Monorepo-`pnpm-lock.yaml`):**

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/dashboard run lint
pnpm --dir apps/dashboard test
```

(Lokal: `pnpm install` ohne `--frozen-lockfile` erlaubt Lockfile-Updates; CI nutzt `--frozen-lockfile`.)

**Compose + Healthcheck:**

```bash
# .env.local vollstaendig (siehe .env.local.example)
docker compose up -d --build
bash scripts/healthcheck.sh
```

## CI (Spiegel)

- **python**: Shell-`bash -n`, pip/Ruff/Black, Schema, **Migrate**, Unit-Pytest + Coverage, **check_coverage_gates**, Integration-Pytest (DB/Redis), Upload `coverage.xml`.
- **dashboard**: Node 20, pnpm-Cache, `pnpm install --frozen-lockfile`, Dashboard lint/test.
- **compose_healthcheck**: generierte `.env.local`, voller Compose-Up, Healthcheck mit Wiederholungen.

## Verbote (Tests)

- Keine echten API-Keys, keine Produktions-DSNs im Repo.
- Keine `assert True` ohne Verhaltensbezug.
- Keine festen absoluten Pfade; Pfade relativ zum Repo-Root.
- Keine unnoetigen `sleep()` — Netzwerk/LLM mocken.

## Logging in Tests

- Keine Secrets in Ausgabe; Fehlertexte kurz halten.

## Coverage ausbauen

- Kritische Liste in `tools/check_coverage_gates.py` bei neuen Pflicht-Modulen anpassen.
- `omit` in `pyproject.toml` / `.coveragerc` nur bewusst aendern und Doku pflegen.
