# BROKEN_BUTTONS — Sprint 1 Prompt B (2026-04-08)

## E2E — sichere Interaktionen

| Oberfläche | Aktion | Spec |
|------------|--------|------|
| Live-Terminal | „Daten aktualisieren“ / `data-testid=live-terminal-reload` | `broken-interactions.spec.ts` |
| Live-Terminal | Technische Details `<details>` aufklappen | dieselbe Spec |
| Signale | Zeitfenster-Link **5m** | dieselbe Spec |
| System & Status (Health) | Quick-Action „Diagnose öffnen“ / „Open diagnostic“ | dieselbe Spec |

## Locale / stille Fehler

- Locale-Mirror: weiterhin **kein** leeres `.catch(()=>{})` (Sprint 1 Vorlauf); siehe `best-effort-fetch` Tests.

## Count

| Metrik | Wert |
|--------|------|
| Nachgewiesene tote Buttons auf Kernpfaden | **0** |
| **blocked** (bewusst nicht klickbar in E2E) | **0** |

## Offen (P1-2)

- Matrix für Self-Healing-Aktionen, Operator-Explain-Submit, Commerce — Zustandsdiagramm + dedizierte Specs.
