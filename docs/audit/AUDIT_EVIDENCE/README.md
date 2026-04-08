# AUDIT_EVIDENCE

Wiederholbare Sammlung von **Kommandoausgaben**, **Inventaren** und (wenn ausgeführt) **E2E-/Stack-Logs**.

## Läufe (append-only)

| Lauf-ID      | Datum (UTC) | Kurzbeschreibung                          |
| ------------ | ----------- | ----------------------------------------- |
| RUN_2026-04-08 | 2026-04-08  | Erstaudit Prompt A — statisch + Toolliste |
| RUN_SPRINT1_2026-04-08 | 2026-04-08 | Prompt B Sprint 1 — E2E Spec, Locale-Mirror, validate_env help |

## Nutzung

- Neue Läufe: Datei `RUN_YYYY-MM-DD.md` anlegen oder bestehende RUN-Datei **an den Anhang** ergänzen.
- Keine Screenshots in Git, wenn sie Secrets zeigen könnten — stattdessen beschreibende Texte + redigierte Snippets.

## Haupt-Artefakte (übergeordnet: `docs/audit/`)

- [`../AUDIT_REPORT.md`](../AUDIT_REPORT.md) — Gesamtvorbericht
- [`../AUDIT_SCORECARD.md`](../AUDIT_SCORECARD.md) — Bewertung 0–11
- [`../AUDIT_BACKLOG.md`](../AUDIT_BACKLOG.md) — Priorisiertes Backlog + Prompt-B-Plan

## Dateien in diesem Ordner

- `RUN_2026-04-08.md` — Baseline-Befehle (git, playwright --list, Hinweise)
- `ROUTE_INVENTORY_DASHBOARD.md` — Next.js `page.tsx` unter `apps/dashboard`
- `API_ROUTES_DASHBOARD.md` — BFF `route.ts` unter `apps/dashboard`
- `BROKEN_LINKS.md` — Platzhalter bis vollständiger Crawl mit laufendem Stack
- `BROKEN_BUTTONS.md` — Platzhalter bis „Broken interaction detector“
- `INCOMPLETE_PAGES.md` — Abgleich mit `PAGE_COMPLETION_MATRIX.md`
