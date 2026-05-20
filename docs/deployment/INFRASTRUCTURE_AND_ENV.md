# Infrastruktur & Environments

Dieses Dokument beschreibt die Laufzeitumgebungen, den Bootstrapping-Prozess und die CI/CD-Pipelines des `BitgetKiTrading`-Projekts, abgeleitet aus dem Quellcode.

## 1. Execution Tiers & Runtimes (Betriebsumgebungen)

Das System klassifiziert Laufzeit- und Ausführungsebenen zentral in `config/execution_runtime.py` und `config/execution_tier.py`.

Die Semantik der Umgebung wird durch die Umgebungsvariablen `APP_ENV`, `PRODUCTION` und `EXECUTION_MODE` definiert:
- **Deployments:** `local`, `development` (bzw. `test`), `production`, `non_production`.
- **Trading Planes (Execution Modes):**
  - `paper`: Reine Papiersimulation, liest Signale. Standard.
  - `exchange_sandbox`: Wenn `BITGET_DEMO_ENABLED=true` gesetzt ist (Demokonto des Brokers).
  - `shadow`: Shadow-Mode. Erstellt Execution-Pläne als wäre es Live, aber führt keine echten Orders aus (`shadow_decision_journal` ist aktiv).
  - `live`: Echtes Trading. `live_order_submission_enabled` und `private_exchange_access_enabled` sind aktiv.
- **Automatisierung:** Wenn der `strategy_execution_mode` auf `auto` steht und Live-Orders erlaubt sind, schaltet das System in den vollautomatischen Modus. Andernfalls liegt eine `manual_strategy_holds_live_firewall` vor.

### Shadow / Live Mirroring
Das System erlaubt eine deterministische Spiegelung (Shadow-Live-Divergence). Im Shadow-Mode generiert der Broker exakte Transaktions-Vektoren, die mit dem Live-Verhalten abgeglichen werden (Sicherheitsmechanismus: `shadow_live_gate_blocks_24h`), ohne Kapital zu riskieren.

---

## 2. Der Bootstrapping- & Initialisierungsprozess

Die Stack-Initialisierung durchläuft eine strikte Boot-Kette, gesteuert über Skripte im `/scripts`-Ordner (z.B. `bootstrap_stack.sh`).

### Boot-Kette
1. **Profil-Auflösung:** Startskripte wie `start_local.sh` rufen intern `bootstrap_stack.sh local` auf. Das Skript lädt die zugehörige `.env.local` (oder `.env.shadow`, `.env.production`).
2. **Pre-Flight-Checks:**
   - Werkzeuge wie `compose_start_preflight.py` und `validate_env_profile.py` prüfen das ENV-File auf Fehler.
   - JWT-Minting: In Shadow/Local wird via `mint_dashboard_gateway_jwt.py` ein Token (`DASHBOARD_GATEWAY_AUTHORIZATION`) für die BFF-to-Gateway Kommunikation generiert.
3. **Datastore-Start:** `docker compose up -d postgres redis` initiiert die In-Memory- und Persistence-Schichten.
4. **Migrationen (infra/migrate.py):** Bevor die Engines starten, werden PostgreSQL-Schema-Migrationen ausgeführt. 
   - Ein Advisory-Lock (`0x62_69_74_67_65_74`) verhindert Race-Conditions.
   - Es wird streng gegen `app.schema_migrations` geprüft. 
   - Optional können Demo-Seeds eingespielt werden (`BITGET_ALLOW_DEMO_SCHEMA_SEEDS`), was jedoch in Produktion (`PRODUCTION=true`) blockiert wird.
   - Die Schema-Version wird zusätzlich durch `config/schema_master.hash` validiert, um Datenbank-Drift zu verhindern.
5. **App-Bootstrapping (`config/bootstrap.py`):**
   - Microservices initialisieren sich via `bootstrap_from_settings()`.
   - Das Logging startet (`log_startup_line`), und `validate_required_secrets` erzwingt das Vorhandensein aller konfigurierten Keys.
   - In Logs werden Secrets explizit durch `***` unkenntlich gemacht (`redact_settings_dict`).
6. **Container Staggering:** Die Container werden hierarchisch gestartet: Core-Feeds -> Engines -> Broker -> Gateways.

---

## 3. Konfigurations- & Secret-Hardening

### Secrets & Validierung
Die Datei `config/required_secrets_matrix.json` diktiert die strikte Anwesenheit von Secrets für jedes Profil (`local`, `staging`, `production`).

**Auszug zwingender Secrets (Production):**
| Environment Variable | Geltungsbereich (Services) | Bedingung (Production) |
| :--- | :--- | :--- |
| `POSTGRES_PASSWORD` | `*` (Alle) | required |
| `DATABASE_URL` / `DATABASE_URL_DOCKER` | `*` (Alle) | required |
| `REDIS_URL` / `REDIS_URL_DOCKER` | `*` (Alle) | required |
| `JWT_SECRET` | `*` (Alle) | required |
| `ADMIN_TOKEN` | `*` (Alle) | required |
| `ENCRYPTION_KEY` | `*` (Alle) | required |
| `INTERNAL_API_KEY` | `*` (Alle) | required |
| `GATEWAY_JWT_SECRET` | `api-gateway` | required |
| `NEXT_PUBLIC_API_BASE_URL` | `*` (Alle) | required |
| `DASHBOARD_GATEWAY_AUTHORIZATION`| `*` (Alle) | required |
| `APEX_AUDIT_LEDGER_ED25519_SEED_HEX`| `audit-ledger` | required |

### Pre-Flight-Absicherung (`config/bootstrap_env_checks.py`)
Das System stoppt den Boot-Prozess (Fail-fast) unter folgenden Bedingungen:
- **Loopback in Produktion:** In Profilen `staging`, `shadow`, oder `production` dürfen URLs (z.B. `API_GATEWAY_URL`, `DATABASE_URL`, `CORS_ALLOW_ORIGINS`) **nicht** `localhost` oder `127.0.0.1` enthalten.
- **Schwache Secrets:** Ein `INTERNAL_API_KEY` unter dem `MIN_PRODUCTION_SECRET_LEN` Limit oder mit schwachen Dummy-Werten (`changeme`, `test`) wird abgelehnt.
- **Docker Compose Namensauflösung:** Es wird verhindert, dass interne Docker-DNS-Namen (wie `http://api-gateway:8000`) fälschlicherweise in `NEXT_PUBLIC_WS_BASE_URL` gelangen, da diese vom Host-Browser nicht auflösbar wären.

---

## 4. CI/CD Pipeline & Release Gates

Die GitHub Actions Pipeline (`.github/workflows/ci.yml`) definiert einen umfassenden, strikten Freigabeprozess:

### Pipeline-Struktur
1. **Python Quality & Tests:**
   - **Linting & Formatting:** `Ruff` und `Black` (streng formatierter Code).
   - **Type Checking:** `Mypy` auf kritische Module (`risk_engine.py`, `exit_engine.py`, `leverage_allocator.py`).
   - **Security / Supply Chain:** `pip-audit` scannt auf Schwachstellen (Blockierung bei CVSS >= 7). Es wird das Secret-Verhalten validiert (`check_production_env_template_security.py`).
   - **Testing:** `pytest` Unit- und Integration-Tests mit blockierenden Coverage-Gates (`check_coverage_gates.py`).
2. **Dashboard & Frontend:**
   - Typ-Prüfung (`pnpm check-types`), Prettier-Validierung.
   - `Jest` Tests, UI-Build und Node `pnpm audit` (high+ vulnerabilities).
3. **Compose Healthcheck & Playwright E2E:**
   - Der Job initiiert einen lokalen Minimal-Stack (`postgres`, `redis`, `api-gateway`, `dashboard`).
   - Das System muss stabil in den `healthy`-Zustand übergehen.
   - **Playwright E2E (`pnpm e2e`):** Automatisierte Nutzerreisen gegen das Frontend auf Port `3000`.
4. **Zentrales Release Approval Gate:**
   - Dieser Job ist von allen vorherigen Jobs (Python, Dashboard, Compose) abhängig.
   - Es führt zusätzlich einen REPO-Freeze-Check durch (`check_release_approval_gates.py`), der sicherstellt, dass keine P0/P1-Bugs als `OPEN` markiert sind und Versionen übereinstimmen (`package.json` und `pyproject.toml`).
   - Nur wenn dieses Gate grün ist, darf ein Deployment auf Production erfolgen.
