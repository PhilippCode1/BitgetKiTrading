# Entwickler Onboarding

Willkommen im BitgetKiTrading Projekt. Dieses Dokument beschreibt den initialen Setup-Prozess für die Entwicklung und das Testen.

## 1. Systemvoraussetzungen
Um lokal an der Plattform arbeiten zu können, müssen zwingend folgende Werkzeuge auf dem Host-System installiert sein:
- **Docker & Docker Compose**: Für die Container-Infrastruktur (Postgres, Redis, Nginx, Microservices).
- **Node.js (LTS) & pnpm**: Für die Dashboard-Frontend-Entwicklung (`/apps/dashboard`).
- **Python 3.12+**: Für die Backend-Services und den `bootstrap_stack.sh` Wrapper.
- **Rust (cargo)**: Für die Kompilierung der performanten `shared_rs` Bibliotheken via Maturin.

## 2. Setup-Prozess & Konfiguration

1. **Repository klonen**: 
   Das Repo in das gewünschte Arbeitsverzeichnis klonen und in den Ordner wechseln.
2. **Environment konfigurieren**:
   Im Root-Verzeichnis existieren Vorlagen. Erstelle deine eigene `.env` Datei:
   ```bash
   cp .env.template .env
   # API-Keys, Secrets und Redis-URLs anpassen!
   ```
   *Wichtig: Das System nutzt eine strikte Fail-Fast Validierung für fehlende oder fehlerhafte Secrets in den `bootstrap_env_checks`.*
3. **Rust Bibliotheken kompilieren (Optional/falls lokal ausgeführt)**:
   Normalerweise geschieht dies im Docker-Build, aber für lokale Pytest-Runs muss Maturin ausgeführt werden:
   ```bash
   pip install maturin
   maturin develop --release -m shared_rs/Cargo.toml
   ```
4. **Stack initialisieren**:
   Starte den gesamten Stack inkl. Migrationen und Base-Services:
   ```bash
   ./scripts/bootstrap_stack.sh
   # Oder via ./scripts/start_local.sh (macOS/Linux) bzw. start_local.ps1 (Windows)
   ```

## 3. Testing & CI Pipeline

Das Projekt unterliegt einer Zero-Regression-Policy. Bevor Code in den Main-Branch gemergt wird, muss die Pipeline (`ci.yml`) alle Gates passieren.

- **Backend-Tests (Python)**:
  Wir nutzen `pytest` für automatisierte Tests und `mypy` für strikte Typ-Prüfung.
  ```bash
  pytest shared/python/tests/
  pytest services/
  ```
- **Frontend-Tests (Next.js)**:
  Im Ordner `/apps/dashboard` befinden sich die Unit-Tests sowie End-to-End-Tests (Playwright).
  ```bash
  cd apps/dashboard
  pnpm install
  pnpm test
  # Oder E2E Tests:
  npx playwright test
  ```
- **Linting**:
  Über 2.900 Linting-Regeln wurden bereinigt. Im CI-Prozess werden sie mit `ruff` (Python) und `eslint` (TypeScript) enforced. Warnungen sind strengstens verboten.
