# BROKEN_LINKS — Sprint 1 Prompt B (2026-04-08)

**Evidence:** `RUN_PROMPT_B_SPRINT1_2026-04-08.md`, `e2e/tests/broken-interactions.spec.ts`, `release-gate.spec.ts`

## Automatisierte Abdeckung

- **Sidebar:** alle `aside.dash-sidebar a[href^="/"]` von `/console` aus, HTTP 2xx, Shell, keine `pageerror`, keine harten Alert-Banner.
- **Kritische Pfade:** feste Liste `CRITICAL_CONSOLE_PATHS` (Terminal, Signale, Marktuniversum, Health, Diagnose, Self-Healing, Live-Broker, Ops, …).
- **Öffentlich:** `/`, `/welcome`

## Ergebnis-Count

| Metrik | Wert |
|--------|------|
| Bekannte defekte Sidebar-Links | **0** |
| Bewusst **blocked** (kein Crawl) | **0** |

## Restrisiko (P1-1)

- Links **innerhalb** von `main` (Fliesstext, Tabellen, Kacheln), die **nicht** in der Sidebar stehen, sind nicht vollständig enumeriert — nächster Schritt: erweiterter Crawl mit Pfad-Whitelist.
