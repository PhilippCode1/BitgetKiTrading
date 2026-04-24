# System-Audit — Verweis- und Phasen-Master (kanonisch)

**Stand:** 2026-04-24 (Dokumentations-Paritaet P83)  
**Vorgaenger:** 2026-03-30 (Release-Bereinigung widerspruechlicher Phasen-Texter P1–P10)

## Rolle

Diese Datei ist **kein** separater Befundbericht, sondern der **einzige** Ueberblick: welche **technischen Audit-Phasen (1–18)** im **Repository** als **COMPLETED** gelten und wo die **kanonische Detaildoku** liegt. Bei Widerspruch gilt **Code + `docker-compose.yml` + CI + ENV-Validatoren** vor aelterer Prosa in Hilfsdokumenten.

## Technische Phasen 1–18 — Status **COMPLETED** (Software-/Repo-Stand)

Jede Phase ist in Code, Tests oder verbindlicher Doku nachweisbar. **Operative** Freigaben (Bitget, Recht, On-Call) bleiben ausserhalb des Repos; siehe `docs/LAUNCH_DOSSIER.md` und `docs/LaunchChecklist.md` (Management-Signoff).

| Phase | Thema | Erledigt (Kurzanker) |
| ----- | ----- | -------------------- |
| 1 | Baseline & Reproduzierbarkeit (ENV, Compose-Pfade) | `docs/CONFIGURATION.md`, `tools/validate_env_profile.py` |
| 2 | Service-Topologie & Health | `docker-compose.yml`, `infra/service-manifest.yaml`, `scripts/healthcheck.sh` |
| 3 | API-Gateway (Auth, Rate-Limits, BFF) | `services/api-gateway/`, `docs/api_gateway_security.md` |
| 4 | Marktdaten & market-stream (WS/REST, Health) | `services/market-stream/`, `docs/market-stream.md` |
| 5 | Feature / Struktur / Drawing (Pipeline) | `services/feature-engine/`, `structure-engine/`, `drawing-engine/` |
| 6 | Signale, Risk, Uncertainty, Gating | `services/signal-engine/`, `shared/python` Risk/Exit |
| 7 | Paper / Shadow / Live — Modus-Trennung | `docs/execution_modes.md`, `config/settings.py` |
| 8 | Live-Broker, Execution-Binding, Spiegel & Forensik | `docs/live_broker.md`, `services/live-broker/` |
| 9 | Multi-Asset & Instrumentidentitaet (kein stilles BTCUSDT) | `MarketInstrumentFactory`, `BitgetInstrumentIdentity` in `shared/python/src/shared_py/bitget/instruments.py`, Katalog/Metadaten |
| 10 | Dashboard (Next.js standalone, BFF) | `apps/dashboard/`, `output: standalone`, `src/lib/server-env.ts` (Gateway nur serverseitig) |
| 11 | Rollen: Kunden- vs. Operator-UI, Operator-JWT | `docs/dashboard_operator.md`, BFF-Proxies, keine Strategie-Mutation im Browser |
| 12 | LLM / Orchestrator (Nebenpfad) | `services/llm-orchestrator/`, `ai-architecture.md` |
| 13 | Kommerz, Modul-Mate-Gates, Tenant | `shared_py.modul_mate_*`, `docs/commercial_transparency.md` |
| 14 | Alert-, Monitor-Engine, Observability | `docs/observability.md`, Prometheus/Grafana optional |
| 15 | Notfall, Recovery, Kill-Switch | `docs/emergency_runbook.md`, `docs/recovery_runbook.md` |
| 16 | Security & Supply-Chain (CI) | `pip_audit_supply_chain_gate.py`, `check_production_env_template_security.py` |
| 17 | Skalierbarkeit / Stresstest-Tooling (HF-Universe) | `tools/hf_universe_stress.py`, `docs/audit/AUDIT_REPORT.md` (P80) |
| 18 | Dokumentations-Paritaet & Audit-Master (P83) | Diese Datei, `docs/LaunchChecklist.md` (technische Kriterien DONE), `README.md` Production Launch |

## Kanonische Quellen (in dieser Reihenfolge lesen)

1. `docs/REPO_TRUTH_MATRIX.md` — Topologie, Risiken
2. `docs/REPO_FREEZE_GAP_MATRIX.md` — Gap-Matrix (P0 im Software-Sinne geschlossen; Restrisiken ADR-0010)
3. `docs/FINAL_READINESS_REPORT.md` — organisationale vs. technische Luecke
4. `docs/LAUNCH_DOSSIER.md` — Freigabeleiter, Cutover
5. `docs/Deploy.md` — ENV, Profile, Compose
6. `docs/adr/ADR-0001-bitget-market-universe-platform.md` — Zielarchitektur
7. `docs/adr/ADR-0010-roadmap-accepted-residual-risks.md` — bewusste Rest-Nicht-Ziele

## Auditierbarkeit / Abhaengigkeiten

- **Python-Runtime (gepinnt):** `constraints-runtime.txt` — in Service-Dockerfiles und CI mit `pip install -c constraints-runtime.txt` verwenden.
- **Node:** Root-`pnpm-lock.yaml` — `pnpm install --frozen-lockfile`.
- **Formale SBOM (CycloneDX/SPDX):** optional; `docs/REPO_SBOM_AND_RELEASE_METADATA.md`, `infra/service-manifest.yaml`.

## Regel bei Widerspruch

Gilt **Code + Compose + CI + ENV-Validatoren** vor alter Markdown-Prosa. Doppelte oder historische Widersprueche in Einzeldateien (z. B. alte Audit-Runs) sind **nicht** massgeblich, wenn sie obige Quellen widersprechen; nachziehen oder im Archiv lassen.

## Regel: Code-Beispiele in der Doku

- **Mehr-Asset / Instrument:** bevorzugt Muster `MarketInstrumentFactory`, `BitgetInstrumentIdentity`, familiengetriebene Konfiguration — keine stillen `BTCUSDT`-Defaults in neuen Beispielen.
- **Trennung Rollen / Gateway:** serverseitig `API_GATEWAY_URL` / `serverEnv` in BFF; oeffentlich nur `NEXT_PUBLIC_*` laut `apps/dashboard/public-env-allowlist.cjs`.
