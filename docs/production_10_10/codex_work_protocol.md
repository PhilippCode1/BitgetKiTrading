# Codex Work Protocol

Dieses Protokoll ist fuer alle Codex-, Cursor- und KI-Agenten im Repository
`bitget-btc-ai` verbindlich. Es konkretisiert `AGENTS.md` fuer taegliche
Arbeit und wird durch `cursor_work_protocol.md`, `private_owner_scope.md` und
`main_console_product_direction.md` fuer die private Main-Console-Ausrichtung
ergaenzt.

## 1. Vor jeder Aenderung

1. Pruefe den Worktree mit `git status --short`.
2. Identifiziere relevante Dateien ueber schnelle Suche oder PowerShell, falls
   `rg` nicht verfuegbar ist.
3. Lies die naheliegenden Service-, Test- und Doku-Dateien.
4. Klassifiziere die Aenderung:
   - Trading/Risk/Live-Broker
   - Security/Auth/Secrets
   - Private Owner/Main Console
   - Legacy-Tenant/Billing/Customer
   - Runtime/ENV/Deployment
   - UI/Main Console/Operator
   - CI/Release/Recovery/Monitoring
5. Benenne Live-Geld-Auswirkungen. Wenn unklar: blockierend behandeln.

## 2. Planungsregel

Fuer nicht-triviale Aenderungen muss Codex einen kurzen Plan bilden:

- Ziel
- betroffene Komponenten
- Risiko- und Fail-closed-Auswirkungen
- Tests/Checks
- Doku/Evidence

Der Plan darf nicht als Ersatz fuer Umsetzung oder Verifikation dienen.

## 3. Implementierungsregel

- Aenderungen minimal-invasiv halten.
- Bestehende Architektur und lokale Patterns verwenden.
- Keine Live-Defaults aktivieren.
- Keine echten Secrets erzeugen oder ausgeben.
- Fail-closed-Pfade erhalten oder staerken.
- Keine fremden Worktree-Aenderungen zuruecksetzen.
- ENV-Aenderungen nur mit Beispielwerten und Doku.

## 4. Risk- und Live-Checkliste

Bei jeder Aenderung an Trading, Risk, Broker, Gateway, ENV, Dashboard, Main
Console oder Legacy-Tenant-/Billing-/Customer-Pfaden muss Codex pruefen:

- Kann diese Aenderung echte Orders erleichtern?
- Bleibt Paper/Shadow der sichere Default?
- Sind `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true` und
  `LIVE_BROKER_ENABLED=true` weiterhin nur Teil einer vollstaendigen Gate-Kette?
- Blockiert das System bei Redis-/DB-/Provider-/Exchange-Fehlern?
- Sind Kill-Switch, Safety-Latch und Reconcile-Divergenz weiterhin bindend?
- Sind Operator-/Owner-Release durch Philipp, Shadow-Match, Risk-Governor,
  Asset-Freigabe, Datenqualitaet und Liquiditaet weiterhin erforderlich?
- Koennen Secrets, Kundendaten oder API-Keys in Logs, Browser oder Tests
  erscheinen?
- Wird Billing, Customer, Sales, Payment oder Subscription versehentlich als
  Produktziel ausgebaut?
- Bleiben neue und geaenderte UI-Texte deutsch und auf die Main Console
  ausgerichtet?

Wenn eine Antwort unsicher ist, gilt die Aenderung als nicht fertig.

## 5. Testregel

Codex muss passende Tests auswaehlen und ausfuehren. Mindestbasis fuer
Production-Readiness-Doku-Aenderungen:

```bash
python tools/release_sanity_checks.py
python tools/check_release_approval_gates.py
pnpm format:check
```

Wenn ein Tool fehlt oder wegen lokaler Umgebung scheitert:

- exakten Befehl nennen
- Exit-Code nennen
- relevante Fehlermeldung zusammenfassen
- einordnen: Repo-Blocker, lokaler Umgebungsblocker oder externer Blocker

Bei Codeaenderungen muessen zusaetzlich die betroffenen Unit-/Integrationstests
laufen. Oberflaechliche Tests, die nur Dateiexistenz pruefen, reichen nicht.

## 6. Dokumentationsregel

Doku muss angepasst werden, wenn sich eines davon aendert:

- ENV-Variable oder Secret-Quelle
- API-/BFF-Vertrag
- Trading- oder Risk-Verhalten
- Live-Broker-Gate
- Private-Owner-, Main-Console- oder Legacy-Tenant-/Billing-/Customer-Policy
- Dashboard-/Operator-Workflow
- Recovery-, Monitoring- oder Release-Prozess
- CI-/Deployment-Verhalten

Production-Readiness-Aussagen muessen auf konkrete Evidence verweisen.

## 7. Evidence-Regel

Jede Abschlussmeldung muss enthalten:

- Dateien: erstellt/geaendert
- Befehle: ausgefuehrt mit Ergebnis
- Tests: bestanden/fehlgeschlagen/nicht ausgefuehrt
- Korrekturen: was nach einem Fehler geaendert wurde
- Restrisiken: besonders externe Go-Live-Abhaengigkeiten
- Live-Geld-Status: weiterhin blockiert ja/nein
- Naechster Schritt

Erlaubte Statusworte: `missing`, `partial`, `implemented`, `verified`,
`external_required`.

## 8. Selbstkorrektur

Wenn eine Pruefung fehlschlaegt:

1. Ursache analysieren.
2. Fehler korrigieren, sofern er im eigenen Aenderungsbereich liegt.
3. Pruefung erneut ausfuehren.
4. Wiederholen, bis der Check gruen ist oder ein externer Blocker eindeutig
   dokumentiert ist.

Nicht selbst verursachte, fremde Worktree-Aenderungen werden nicht revertiert.

## 9. Abschlussverbot

Codex darf nicht "fertig" melden, wenn:

- relevante Tests nicht gelaufen sind und kein Grund genannt wurde
- ein Check fehlschlaegt und die Ursache nicht dokumentiert ist
- Risk-/Live-Auswirkungen unbewertet sind
- Doku/Evidence fehlt
- Secrets oder Kundendaten exponiert sein koennten
- Live-Geld nicht nachweislich blockiert bleibt

## 10. Repo-spezifische Kernbefehle

```bash
python tools/release_sanity_checks.py
python tools/check_release_approval_gates.py
python tools/production_readiness_audit.py
python tools/production_readiness_audit.py --strict
python tools/validate_env_profile.py --env-file .env.local --profile local
python tools/validate_env_profile.py --env-file .env.production --profile production
python tools/inventory_secret_surfaces.py
python tools/verify_production_secret_sources.py
python tools/verify_alert_routing.py
pnpm format:check
pnpm check-types
pnpm test
```
