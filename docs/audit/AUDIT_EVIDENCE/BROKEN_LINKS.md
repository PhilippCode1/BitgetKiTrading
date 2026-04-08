# BROKEN_LINKS — Nach Sprint 1 (Prompt B) + Prompt A 2026-04-07

**Letzte Audit-Referenz:** `RUN_2026-04-07_PROMPT_A_ROUND3.md` (kein neuer Playwright-Gesamtlauf auf diesem Host).  
**Marktuniversum:** Release-Gate prueft Sichtbarkeit von `data-testid="market-universe-lineage"` (siehe `release-gate.spec.ts`).

## Automatisierte Abdeckung

- **Playwright:** `e2e/tests/broken-interactions.spec.ts` traversiert alle `aside.dash-sidebar a[href^="/"]` ausgehend von `/console` und prueft HTTP-2xx sowie zieltyp-spezifische Shell (`/`, `/onboarding`, `/console`).
- **Release-Gate:** weiterhin `e2e/tests/release-gate.spec.ts` (Kern-API + ausgewaehlte Konsole-Pfade).

## Ergebnis-Count (bewiesen lokal in Sprint 1)

| Metrik | Wert |
|--------|------|
| Defekte Sidebar-Links (manuell gemeldet) | 0 |
| E2E-Lauf gegen Live-URL in diesem Dokument | *CI / lokaler Stack: Nutzer ausfuehren* |

## Restrisiko (P1)

- Links **ausserhalb** der Sidebar (Fliesstext, Kacheln, Admin-Untermenues ohne Nav-Eintrag) sind nicht durch die Sidebar-Spec abgedeckt — Follow-up: erweiterte Spec oder Crawl ab `/console` mit erlaubter Pfadliste.

## Blocked / erwartet anders

- Keine bekannten bewussten Ausnahmen; Admin-Routen erscheinen nur bei `showAdminNav` und werden mit traversiert, falls Link sichtbar.
