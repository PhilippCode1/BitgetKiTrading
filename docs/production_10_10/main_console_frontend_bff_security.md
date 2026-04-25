# Main Console Frontend- und BFF-Sicherheit

## Ziel

Die Main Console bleibt fuer Philipp einfach bedienbar, aber strikt sicher:
keine Secrets im Browser, klare deutsche Fehlermeldungen, redacted Payloads und
fail-closed Verhalten bei unklaren Datenquellen.

## Verbindliche Regeln

1. Keine Bitget/OpenAI/Telegram/DB/Redis/JWT/Internal-Secrets im Browser.
2. `NEXT_PUBLIC_*` enthaelt nur nicht-sensitive Werte.
3. BFF nutzt server-only Konfiguration (`server-env.ts`, `gateway-bff.ts`).
4. Fehler werden redacted und deutsch dargestellt.
5. Loading-/Unknown-/Empty-State zeigen keine Fake-Gruenlogik.
6. Unbekannte Backend-Lage fuehrt zu warnendem/blockierendem Zustand.
7. Aktive Main-Console-Flows enthalten keine neuen Billing-/Customer-/SaaS-Texte.
8. Gefaehrliche Aktionen duerfen nicht rein clientseitig freigegeben werden.

## Technische Umsetzung

- `apps/dashboard/src/lib/server-env.ts`
  - server-only Variablen fuer Gateway/Auth.
- `apps/dashboard/src/lib/gateway-bff.ts`
  - deutsches, klares Fehlerbild bei fehlender Gateway-Auth.
- `apps/dashboard/src/lib/user-facing-fetch-error.ts`
  - Fehlerklassifikation + deutsche Nutzertexte, ohne Secret-Leak.
- `apps/dashboard/src/lib/private-credential-view-model.ts`
  - fail-closed bei unknown/not connected, nur redacted hints.
- `tools/check_main_console_frontend_security.py`
  - statische Guards gegen gefährliche Patterns.

## Statische Sicherheitschecks

Der Checker prueft mindestens:

- gefaehrliche `NEXT_PUBLIC_*` Secret-Namen in `.env*.example`
- `dangerouslySetInnerHTML`
- `target="_blank"` ohne `rel`
- `console.log` in sensitiven Kontexten
- deutsche BFF-Fehlermeldung und Server-Only-Auth-Guard
- aktive Main-Console-Dateien auf neue Billing/Customer/SaaS-Begriffe

## Offene Frontend-E2E-Pruefung

Als naechster Schritt bleibt eine echte Browser-E2E-Pruefung sinnvoll:

- Missing-Gateway-Auth simulieren und deutschen Error-Banner verifizieren.
- Unknown-Backend fuer zentrale Karten simulieren und Live-Blockhinweis pruefen.
- Sicherstellen, dass Netzwerk-Responses keine Secret-Felder enthalten.
