# Prompt A — Runde 5 · Baseline & Laufzeit (2026-04-08)

**Branch:** `master`  
**HEAD:** `e871b871b4a8cd803edcec50ca763e50cad7078c`  
**Arbeitsbaum:** **clean** (`git status` leer zum Audit-Zeitpunkt)

## Ausgeführte Checks

| Befehl | Ergebnis |
|--------|----------|
| `docker compose -f docker-compose.yml config --quiet` | Exit **0** |
| `docker compose ps` | Alle gelisteten Services **Up (healthy)** (Container-Ebene) |
| `pnpm check-types` (turbo) | **OK** |
| `python -m pytest tests/llm_eval -q` | **23 passed** (~39 s) |
| `pnpm rc:health` | **FAIL / instabil** in diesem Lauf — siehe unten |

## `pnpm rc:health` — Beobachtung (kritisch)

Während des Laufs traten u. a. auf:

- HTTP-Timeouts gegen `http://127.0.0.1:8000/ready` und `v1/system/health`
- `system-health`: mehrere Dienste **nicht ok** (u. a. `market-stream`, `signal-engine`, `feature-engine`, …)
- `http://localhost:3000/api/health` → Timeout
- **`GET /ready` (api-gateway):** `ready: false` mit **`redis: Timeout reading from socket`** (Postgres ok)

**Interpretation:** Trotz `docker compose ps` = healthy kann die **Laufzeitlage** (Gateway↔Redis, Worker-Ready) **degradiert** sein — **kein Widerspruch**, weil Healthchecks andere Probes nutzen können als synchroner Redis-Read im Gateway.

**Prompt B / SRE:** Redis-Verbindungsstabilität, Timeouts, Pooling, `maxclients`, Netzlast, sowie klare **UI-/Runbook-Anzeige** wenn `core_redis: false`.

## Nicht ausgeführt

- Vollständiger `pnpm e2e` in Runde 5 (abhängig von stabilem Gateway/Dashboard)
- `config:validate` gegen produktive `.env.local` mit echten Secrets

## Referenz früher grüner Lauf

`RUN_PROMPT_B_SPRINT1_2026-04-08.md` dokumentierte `rc:health` Exit 0 unter günstigerer Laufzeitlage — **Reproduzierbarkeit schwankt**.
