# Single-Admin Entry Flow

## Zielroute

- Kanonische Startroute ist `/console`.
- Root `/` leitet serverseitig auf `/console` um.
- Ohne gesetzte Locale leitet Middleware auf
  `/welcome?returnTo=/console`.

## Auth-Annahme

- Produktion: Zugriff auf sensible Operator-Funktionen basiert auf
  `DASHBOARD_GATEWAY_AUTHORIZATION` und Admin-Claims.
- Lokal: Main Console darf fuer Entwicklung erreichbar sein, aber keine
  unsichere Fake-Login-Mechanik fuer Produktion.
- Wenn Admin-Session fehlt, bleiben Admin-Unterseiten blockiert/umgeleitet.

## ReturnTo-Regeln

- Erlaubt sind interne Pfade unter:
  - `/console`
  - `/onboarding`
  - `/welcome`
- Legacy `/ops` wird intern auf `/console/ops` normalisiert.
- Leerer, kaputter oder root-basierter Ruecksprung faellt auf `/console`.

## Open-Redirect-Schutz

- Externe Ziele wie `https://...` werden verworfen.
- Protokoll-relative Ziele wie `//evil.example` werden verworfen.
- Nur interne relative Pfade werden akzeptiert.

## Single-Admin-Betrieb

- Einstieg ist auf eine interne Konsole ausgerichtet, nicht auf oeffentliche
  oder kundenorientierte Landingpages.
- Welcome bleibt kurz, deutsch und funktional (Sprache setzen, sicher weiter).

## No-Go

- Keine Public-/Customer-/Sales-Startseite als produktiver Einstieg.
- Kein Redirect auf externe Domains ueber `returnTo`.
- Kein unsicherer Produktions-Bypass ohne Auth-Kontext.
