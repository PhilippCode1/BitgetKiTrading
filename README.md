# BitgetKiTrading - Enterprise-Grade AI Trading System

BitgetKiTrading ist ein hochgradig deterministisches, latenzoptimiertes und KI-gestütztes Trading-System, das auf absolute Produktionsreife, Sicherheit und Ausfallsicherheit (Zero-Regression) ausgelegt ist. Das System kombiniert latenzkritische Orderbuch-Verarbeitung in Rust mit fortgeschrittenen Machine-Learning-Strategien in Python und einer modernen, responsiven Steuerzentrale in Next.js.

## Tech-Stack
- **Core Backend**: Python 3.12+ (Microservices, ML/AI Engines)
- **High-Performance Extensions**: Rust (via PyO3/Maturin) für Indikatoren (`apex_core`), Orderbuch und Shared Memory IPC
- **Frontend / Operator Console**: Next.js (App Router), TypeScript, React Query, TailwindCSS
- **Messaging & Eventbus**: Redis Streams (Event-Driven Architecture)
- **Databases**: PostgreSQL (Relational Data), TimescaleDB (Time-Series Data), Redis (In-Memory State & Pub/Sub)
- **Infrastruktur**: Docker, NGINX Reverse Proxy, Prometheus & Grafana (Observability)

## Inhaltsverzeichnis (Dokumentation)

Die gesamte Systemdokumentation ist nach einem "Tabula Rasa" Ansatz strikt aus der aktuellen "Code as Truth"-Perspektive generiert worden.

### System-Design & Infrastruktur
- [System Architecture](docs/architecture/SYSTEM_DESIGN.md)
- [Infrastructure & Deployment](docs/deployment/INFRASTRUCTURE_AND_ENV.md)

### Microservices & Kerndienste
- [Live Broker (Execution & Safety)](docs/services/LIVE_BROKER.md)
- [Signal & Market Engine](docs/services/SIGNAL_AND_MARKET_ENGINE.md)
- [AI & Learning Engine](docs/services/AI_AND_LEARNING_ENGINE.md)
- [Shared Core (Python & Rust)](docs/services/SHARED_CORE.md)

### Frontend & Dashboards
- [Dashboard Architecture](docs/frontend/DASHBOARD_ARCHITECTURE.md)

### Operation & Onboarding
- [Entwickler Onboarding](docs/ONBOARDING.md)
- [Operator Manual (Runbook)](docs/runbooks/OPERATOR_MANUAL.md)

## Quick Start

Lokales Bootstrapping für Entwicklungszwecke:

**Linux / macOS:**
```bash
./scripts/start_local.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\start_local.ps1
```
Dies lädt die lokalen Profile, startet die benötigten Docker-Container und initialisiert die Datenbank-Migrationen.
