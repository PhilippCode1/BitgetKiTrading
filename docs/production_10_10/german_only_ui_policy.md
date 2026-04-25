# German-only UI Policy

## 1) Ziel

`bitget-btc-ai` wird als private deutsche Hauptkonsole fuer Philipp Crljic
betrieben. Die sichtbare Produktoberflaeche ist deutsch.

## 2) Erlaubte technische Ausnahmen

Technische Bezeichner duerfen intern englisch bleiben, wenn sie nicht als
Benutzerfuehrung erscheinen:

- ENV-, API-, Header-, Feld- und Tabellen-Namen
- technische Protokollbegriffe (z. B. `SSE`, `JSON`, `WebSocket`)
- eindeutige IDs und interne Diagnoseschluessel

Die verbindlichen Begriffe stehen in
`docs/production_10_10/german_ui_glossary.md`.

## 3) Verbindliches Glossar

Die Hauptbegriffe fuer Navigation, Buttons, Warnungen und Status werden aus dem
Glossar uebernommen. Keine sichtbaren Alternativen wie `Health & incidents`,
`Operator approval`, `Billing`, `Customer`, `Pricing` oder `Sales`.

## 4) Regeln fuer Fehlermeldungen

- Fehlertexte sind deutsch, kurz und handlungsorientiert.
- Jede Fehlermeldung benennt naechsten Schritt (z. B. neu laden, Diagnose
  oeffnen, Betrieb informieren).
- Keine Secret-Werte oder sensible interne Details im UI-Fehlertext.

## 5) Regeln fuer Empty States

- Jede leere Ansicht hat deutschen Titel + kurzen Erklaertext.
- Leere Tabellen/Listen enthalten mindestens einen sinnvollen naechsten Schritt.
- Kein stilles Leerrendering fuer Live-/Risk-relevante Bereiche.

## 6) Regeln fuer Live-/Risk-Warnungen

- Warnungen fuer Echtgeldmodus, Risiko, Not-Stopp, Sicherheits-Sperre, Abgleich
  und Live-Blocker sind deutsch und unmissverstaendlich.
- Bei Unsicherheit gilt fail-closed Sprache (blockierend, nicht verharmlosend).
- Begriffe fuer Modi: Papiermodus, Schattenmodus, Echtgeldmodus.

## 7) Regeln fuer KI-Erklaerungen auf Deutsch

- KI-Hinweise, Operator-Erklaerungen und Diagnosezusammenfassungen sind deutsch.
- KI-Texte bleiben beratend, ohne Trading-Freigabecharakter.
- Die UI muss sichtbar machen, dass KI keine automatische Orderfreigabe ist.

## 8) No-Go

- Englische sichtbare Produktnavigation in der finalen Hauptkonsole.
- Billing-/Customer-/Sales-/Pricing-Texte als produktive Hauptnavigation.
- Gemischte Kernlabels wie `Health & incidents`, `Signal-Center`,
  `Self Healing`, `No-Trade`.

## 9) Teststrategie

Statischer Mindestcheck:

```bash
python tools/check_german_only_ui.py
python tools/check_german_only_ui.py --strict
python tools/check_german_only_ui.py --json
pytest tests/tools/test_check_german_only_ui.py -q
```

Zusatz bei UI-Aenderungen:

```bash
pnpm --dir apps/dashboard run test:ci
pnpm --dir apps/dashboard run build
pnpm check-types
```

Strict scheitert bei fehlender Policy, fehlendem Glossar, kritischen englischen
sichtbaren Labels, sichtbaren Billing-/Customer-/Sales-Labels und fehlenden
deutschen Main-Console-Kernbegriffen.
