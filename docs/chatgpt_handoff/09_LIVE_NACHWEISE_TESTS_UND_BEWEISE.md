# Live-Nachweise, Tests und Beweise (bitget-btc-ai)

**Ausführungskontext:** Befehle auf einem **Windows**-Host im Projektverzeichnis ausgeführt (PowerShell). **Datum der Läufe:** 2026-04-04.

**Regel:** Alle genannten Ergebnisse stammen **ausschließlich** aus diesen Läufen. Nicht ausgeführte Prüfungen sind als solche gekennzeichnet — **keine** erfundenen Pass/Fail-Angaben.

---

## 1. Kurzfazit mit ehrlichem Gesamtbild

- **Unit-/Komponententests** für ausgewählte **Gateway-LLM-Routen** und **Dashboard-Fehlertext-Mapping** sind in dieser Session **grün** gelaufen (reine Softwareebene, **ohne** laufenden Docker-Stack).
- **Monorepo Typecheck (`pnpm check-types`)** ist **fehlgeschlagen** — das Repo ist in diesem Zustand **nicht** als „TypeScript sauber“ belegt.
- **Smoke (`pnpm smoke`)** ist **nicht** gelaufen — PowerShell bricht mit **Parserfehler** in `scripts/_dev_compose.ps1` ab (Encoding/Zeichen in Strings). Damit ist **kein** Edge-Health über dieses Skript in dieser Session nachgewiesen.
- **API-Integration-Smoke** gegen `http://127.0.0.1:8000` ist für Gateway-Pfade **fehlgeschlagen** (Verbindung verweigert — **kein** lokaler Gateway-Prozess erreichbar). **Ein** öffentlicher Bitget-Schritt lief mit **HTTP 200** — belegt Netz/öffentliche API, **nicht** den lokalen Stack.
- **`production_selfcheck.py`:** Teile ok/skip, **Ruff schlägt fehl** (Zeilenlänge in der Selfcheck-Datei selbst).
- **`prettier --check .`:** **Exit 2** — u. a. **SyntaxError** bei `.github/workflows/ci.yml` im Prettier-Lauf; viele `[warn]`-Dateien. Kein „Format grün“-Nachweis.

**Fazit:** Es gibt **solide isolierte Testnachweise** für Teile der LLM-Gateway- und Dashboard-Fehlerlogik. Ein **betrieblicher** oder **End-to-End-Nachweis** (Compose gesund, Gateway live, Playwright) ist in dieser Session **nicht** erbracht.

---

## 2. Tabelle aller ausgeführten Kommandos

| #   | Kommando                                                                                                                                                   | Zweck                                                          | Exit                                               | Dauer (ca.) |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------- | ----------- |
| 1   | `pnpm check-types` (Repo-Root)                                                                                                                             | `turbo run check-types` (Dashboard + shared-ts laut Turbo)     | **1**                                              | ~29 s       |
| 2   | `python -m pytest tests/unit/api_gateway/test_routes_llm_operator.py -q --tb=no`                                                                           | Gateway-Unit-Tests LLM-Operator-Forward (gemockt)              | **0**                                              | ~57 s       |
| 3   | `cd apps/dashboard && pnpm test -- src/lib/__tests__/operator-explain-errors.test.ts src/lib/__tests__/strategy-signal-explain-errors.test.ts --runInBand` | Jest: Fehler-Mapping Operator/Strategy-Signal                  | **0**                                              | ~15 s       |
| 4   | `pnpm smoke`                                                                                                                                               | `scripts/rc_health.ps1` Edge-/Stack-Gesundheit                 | **1**                                              | ~4 s        |
| 5   | `cd shared/ts && pnpm run check-types`                                                                                                                     | Typecheck shared-ts isoliert                                   | **1** (kein Script)                                | ~3 s        |
| 6   | `python -m pytest tests/llm_orchestrator/test_structured_fake_provider.py -q --tb=no`                                                                      | LLM-Orchestrator Fake-Provider / Structured Output             | **0**                                              | ~42 s       |
| 7   | `python tools/production_selfcheck.py`                                                                                                                     | Selfcheck Migration/shared_py + Ruff-Pflicht                   | **1**                                              | ~6 s        |
| 8   | `Invoke-WebRequest http://127.0.0.1:8000/health -TimeoutSec 2`                                                                                             | Schnellprobe lokaler Gateway                                   | Shell **0**, fachlich **Timeout** (kein HTTP-Body) | ~4 s        |
| 9   | `python scripts/api_integration_smoke.py`                                                                                                                  | Smoke gegen `.env.local` Gateway + öffentlicher Bitget-Schritt | **1**                                              | ~8 s        |
| 10  | `pnpm format:check`                                                                                                                                        | Prettier `--check .`                                           | **2**                                              | ~30 s       |

**Nicht ausgeführt** (kein Anspruch auf Ergebnis): `pnpm e2e`, `bash scripts/healthcheck.sh`, `bash tests/dashboard/test_live_state_contract.sh`, vollständige `pytest`-Gesamtsuite, `pnpm lint` / `turbo run lint`, `python scripts/release_gate.py`.

---

## 3. Tabelle aller erfolgreichen Nachweise

| Nachweis                                                                     | Aussagekraft                                                                                                              | Kurzbeleg                    |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Pytest `test_routes_llm_operator.py` — **5 passed**                          | Mittel: Gateway-LLM-Routen mit Mock-Forward **verhalten sich** wie im Test spezifiziert; **kein** echter Orchestrator     | stdout: `5 passed in 51.03s` |
| Jest Operator/Strategy-Signal-Explain-Errors — **15 passed**                 | Mittel: UI-seitige Fehlerklassifikation/Textsicherheit **für diese Module**                                               | stdout: `Tests: 15 passed`   |
| Pytest `test_structured_fake_provider.py` — **3 passed**                     | Mittel: Fake-Provider liefert schema-konforme Struktur **in Testumgebung**                                                | stdout: `3 passed in 39.16s` |
| `api_integration_smoke.py` Schritt **[4] Bitget public tickers -> HTTP 200** | Niedrig bis mittel: **Öffentlicher** REST-Zugriff von diesem Host aus funktioniert; **kein** Nachweis für interne Dienste | stdout: `api_code=00000`     |

---

## 4. Tabelle aller fehlgeschlagenen oder nicht ausführbaren Nachweise

| Nachweis                           | Ergebnis                | Ursache (wie gemessen)                                                                                                                                                                |
| ---------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm check-types`                 | **Fehlgeschlagen**      | `tsc --noEmit`: u. a. `admin/page.tsx` — `Property 'status' does not exist on type 'SystemHealthResponse'`; `paper/page.tsx` — `account_ledger_recent` optional vs. required mismatch |
| `pnpm smoke`                       | **Nicht ausführbar**    | `ParserError` in `scripts/_dev_compose.ps1` (Zeichenfolge mit `?`/`bitte` — Datei-Encoding/Kette)                                                                                     |
| `shared/ts` `pnpm run check-types` | **Nicht anwendbar**     | `ERR_PNPM_NO_SCRIPT` — im Paket `shared/ts` kein `check-types`-Script (Fehlbedienung / falsche Erwartung)                                                                             |
| `production_selfcheck.py`          | **Fehlgeschlagen**      | `FAIL: ruff check` — `E501` Zeile 221 in `tools/production_selfcheck.py` (97 > 88 Zeichen); davor `OK` Migration/shared_py, `SKIP` ohne `DATABASE_URL`                                |
| HTTP `127.0.0.1:8000/health`       | **Kein Erfolg**         | Ausgabe sinngemäß **Zeitüberschreitung** (deutsche PowerShell-Meldung) bei 2 s — kein erfolgreicher HTTP-Status ausgelesen                                                            |
| `api_integration_smoke.py` gesamt  | **Fehlgeschlagen**      | `[1]`–`[3]` `WinError 10061` Verbindung verweigert zu `http://127.0.0.1:8000`; Script-Ende: `mindestens ein kritischer Schritt fehlgeschlagen`                                        |
| `pnpm format:check`                | **Fehlgeschlagen**      | Exit **2**: Prettier meldet `SyntaxError` für `.github/workflows/ci.yml` („Nested mappings…“); sehr viele weitere `[warn]`-Treffer                                                    |
| Turbo                              | Warnung (kein Testfail) | `fatal: detected dubious ownership in repository` — Git safe.directory (Umgebung)                                                                                                     |

---

## 5. Welche Bereiche praktisch verifiziert sind

- **API-Gateway LLM-Operator-Routen:** Verhalten **unter Testbedingungen** (Mock), siehe Abschnitt 3, Pytest-Datei `test_routes_llm_operator.py`.
- **Dashboard:** Fehlerbehandlung/Mapping für **Operator Explain** und **Strategy-Signal-Explain** in den genannten Jest-Dateien.
- **LLM-Orchestrator:** **Fake-Provider / structured** Pfad in `test_structured_fake_provider.py` (isoliert).
- **Externe Erreichbarkeit:** Mindestens ein **öffentlicher** Bitget-Call aus Schritt [4] des Integration-Smokes mit **HTTP 200** (kein Beweis für Bitget-Keys im Trading-Kontext, nur „öffentlicher Tickers-Call lief“).

---

## 6. Welche Bereiche nur aus Code abgeleitet sind

- **Gesamter Docker-Compose-Lauf**, Readiness aller Worker, echte DB-Queries im Gateway unter Last.
- **SSE `/v1/live/stream`**, Browser-Terminal, echte Kerzen in `tsdb.candles`.
- **Playwright E2E**, `release_gate` mit `--with-e2e`.
- **Produktionsfreigabe** („alles grün“) — **nicht** durch diese Session belegt.

---

## 7. Welche Bereiche komplett offen bleiben

- Laufzeit: **api-gateway + postgres + redis + market-stream + …** zusammen auf diesem Host am Prüfdatum.
- **Authentifizierter** Durchlauf `GET /v1/system/health` mit realem Operator-JWT gegen live Gateway.
- **E2E** `e2e/tests/release-gate.spec.ts` in dieser Session.
- **Shell-Smokes** unter Bash (`healthcheck.sh`, `test_live_state_contract.sh`) auf diesem Windows-Setup ohne WSL-Aufruf.
- **Screenshots** / visuelle Regression: nicht erstellt, nicht angehängt.

---

## 8. Bewertung der Aussagekraft je Test

| Testtyp                              | Aussagekraft                                          | Begründung                                                                  |
| ------------------------------------ | ----------------------------------------------------- | --------------------------------------------------------------------------- |
| Unit-Tests Gateway (mock)            | Mittel                                                | Isoliert Routing/Auth-Annahmen; **kein** Netz, **kein** echter Orchestrator |
| Jest Fehler-Mapping                  | Mittel–hoch für UX-Fehlerpfade                        | Deckt String/HTTP-Mapping ab, **kein** Server-Integrationstest              |
| LLM Fake-Provider Pytest             | Mittel                                                | Beweist Konsistenz **Fake vs. Schema** in Tests, **nicht** OpenAI-Qualität  |
| api_integration_smoke (Gateway down) | **Niedrig** für Stack                                 | Zeigt vielmehr **Abwesenheit** lokaler Edge; Bitget-Schritt separat         |
| Typecheck / Prettier / Ruff          | Hoch für **Repo-Hygiene** wenn grün; hier **negativ** | Aktueller Zustand: **rote** Signale für Release-Disziplin                   |
| smoke/rc_health                      | Hoch **wenn** lauffähig                               | In dieser Session **0** Aussagekraft — Skript startet nicht                 |

---

## 9. Welche zusätzlichen Prüfungen für echte Betriebsfreigabe fehlen

1. **`pnpm check-types` und vereinbarte Lint/Format-Pipelines grün** (aktuell: Typecheck- und Format-/Ruff-Failures).
2. **`pnpm smoke` bzw. `scripts/healthcheck.sh`** auf Zielplattform **ohne** Parserfehler; dann: Gateway `/ready`, `/v1/system/health` mit produktivem JWT.
3. **Vollständiger Compose-Stack** laut `docs/stack_readiness.md` mit `docker compose ps` und erwarteten `healthy`.
4. **`api_integration_smoke.py` Exit 0** mit erreichbarem `API_GATEWAY_URL`.
5. **Playwright** `pnpm e2e` oder CI-Äquivalent mit grünem Lauf.
6. **Manuelle Stichprobe** kritischer Oberflächen (Signale, Terminal, Live-Broker) mit **Screenshots** und Datum in `docs/Cursor/assets/screenshots/` (derzeit kein Nachweis).
7. **Fix** `_dev_compose.ps1` Encoding für Windows-Smokes oder dokumentierter alternativer Pfad (WSL/Git-Bash).

---

## 10. Übergabe an ChatGPT

- **„Tests grün“** ohne Kontext **nicht** über das ganze Repo verallgemeinern: in dieser Akte sind **nur** die genannten Suiten grün.
- **Typecheck/Format** aktuell **rot** — das ist ein **harter** Hinweis gegen „release ready“.
- **Kein lokaler Gateway** am Prüfzeitpunkt: typisch `WinError 10061` / Timeout — **Ursache** fast immer „Stack nicht gestartet“, nicht „Bug in Smoke-Skript“ allein.
- Für **Betrieb** immer **frische** Logs von Gateway + betroffenem Worker anfordern; diese Akte ersetzt **keine** Logdatei.

---

## 11. Anhang mit Rohoutputs, Logausschnitten und Referenzen

### 11.1 Pytest Gateway LLM (Auszug)

```text
.....                                                                    [100%]
5 passed in 51.03s
```

### 11.2 Jest Dashboard (Auszug)

```text
Test Suites: 2 passed, 2 total
Tests:       15 passed, 15 total
Time:        5.848 s
```

### 11.3 Pytest LLM Fake Provider (Auszug)

```text
...                                                                      [100%]
3 passed in 39.16s
```

### 11.4 Typecheck-Fehler (Auszug)

```text
src/app/(operator)/console/admin/page.tsx(18,17): error TS2339: Property 'status' does not exist on type 'SystemHealthResponse'.
src/app/(operator)/console/paper/page.tsx(65,25): error TS2322: Type 'GatewayReadEnvelope & { ... }' is not assignable to type '{ ... account_ledger_recent: PaperLedgerEntry[]; }'.
  Types of property 'account_ledger_recent' are incompatible.
    Type 'PaperLedgerEntry[] | undefined' is not assignable to type 'PaperLedgerEntry[]'.
```

### 11.5 pnpm smoke / PowerShell (Auszug)

```text
In ...\scripts\_dev_compose.ps1:37 Zeichen:43
+         throw "Env-Datei fehlt: $full ?" bitte .env.local.example na ...
+                                           ~~~~~
Unerwartetes Token "bitte" in Ausdruck oder Anweisung.
...
ParserError
```

### 11.6 production_selfcheck (Auszug)

```text
OK: Migration-Datei vorhanden, shared_py importierbar
SKIP: DATABASE_URL nicht gesetzt - keine DB-Pruefung
tools\production_selfcheck.py:221:89: E501 Line too long (97 > 88)
FAIL: ruff check (Selfcheck-Dateien; pip install -r requirements-dev.txt)
```

### 11.7 api_integration_smoke (Auszug)

```text
[1] GET /health -> FAIL <urlopen error [WinError 10061] Es konnte keine Verbindung hergestellt werden, da der Zielcomputer die Verbindung verweigerte>
[2] GET /ready -> FAIL <urlopen error [WinError 10061] ...>
[3] GET /v1/system/health -> FAIL <urlopen error [WinError 10061] ...>
...
[4] Bitget public tickers -> HTTP 200 api_code=00000
ERGEBNIS: mindestens ein kritischer Schritt fehlgeschlagen.
```

### 11.8 Prettier check (Auszug)

```text
[error] .github/workflows/ci.yml: SyntaxError: Nested mappings are not allowed in compact mappings (71:15)
...
Error occurred when checking code style in the above file.
 ELIFECYCLE  Command failed with exit code 2.
```

### 11.9 Referenzen im Repo

| Dokument / Pfad                                      | Nutzen                             |
| ---------------------------------------------------- | ---------------------------------- |
| `docs/stack_readiness.md`                            | Definition „Stack bereit“          |
| `scripts/healthcheck.sh`                             | Bash-Smoke (hier nicht ausgeführt) |
| `scripts/api_integration_smoke.py`                   | HTTP-Smoke inkl. Gateway           |
| `e2e/tests/release-gate.spec.ts`                     | Playwright (hier nicht ausgeführt) |
| `tests/unit/api_gateway/test_routes_llm_operator.py` | Grüner Lauf dokumentiert           |
| `API_INTEGRATION_STATUS.md`                          | Erwartetes Smoke-Verhalten         |

---

_Ende der Beweisakte._
