# Windows: Smoke-Kette und PowerShell-Fix (bitget-btc-ai)

**Dokumenttyp:** Nachweis und Betriebshinweis für `pnpm smoke`, `dev:up`, `stack:check` unter Windows.  
**Stand:** 2026-04-05.  
**Startpunkt:** `docs/chatgpt_handoff/09_LIVE_NACHWEISE_TESTS_UND_BEWEISE.md` (ParserError in `_dev_compose.ps1`).

---

## 1. Ursache (hart)

In mehreren `scripts/*.ps1`-Dateien stand das **Em-Dash** (Unicode **U+2014**, `—`) in **doppelt quotierten** Strings.

**Windows PowerShell 5.1** (Standard bei `powershell.exe` aus `package.json`) interpretiert `.ps1`-Dateien oft als **System-ANSI** oder **UTF-8 ohne BOM**. Die UTF-8-Bytes von U+2014 werden dann **falsch** gelesen; der String wirkt **vorzeitig beendet**, danach erscheint Klartext (`bitte`, `JWT-Mint`, …) **außerhalb** des Strings → **ParserError**.

**Beleg (VORHER, aus Handoff 09 / identisches Muster):**

```text
In ...\scripts\_dev_compose.ps1:37 Zeichen:43
+         throw "Env-Datei fehlt: $full ?" bitte .env.local.example na ...
+                                           ~~~~~
Unerwartetes Token "bitte" in Ausdruck oder Anweisung.
ParserError
```

---

## 2. Umsetzung im Repo

1. **Alle Em-Dash-Zeichen (`—`) in betroffenen `.ps1`-Dateien** durch ASCII **`-`** (Leerzeichen um den Strich) ersetzt.
2. **Kommentarblock** in `scripts/_dev_compose.ps1` ergänzt: keine U+2014 in Strings ohne UTF-8-BOM.
3. **Neues Regression-Skript** `scripts/verify_powershell_syntax.ps1`: parst jede `scripts/*.ps1` mit `[System.Management.Automation.Language.Parser]::ParseFile`.
4. **`package.json`:**
   - `pnpm ps:verify-syntax` → Syntax-Check aller Skripte
   - `pnpm dev:up:help` → ruft `dev_up.ps1 -Help` auf
5. **`dev_up.ps1` / `compose_up.ps1`:** Parameter **`-Help`** (Get-Help, Exit 0).

**Geänderte / neue Dateien:**

| Datei                                    | Änderung                             |
| ---------------------------------------- | ------------------------------------ |
| `scripts/_dev_compose.ps1`               | U+2014 entfernt, Hinweis im Header   |
| `scripts/docker-path.ps1`                | U+2014 in Kommentar                  |
| `scripts/close_local_monitor_alerts.ps1` | U+2014 in Kommentar                  |
| `scripts/rebuild_gateway.ps1`            | U+2014 in Write-Host                 |
| `scripts/collect_release_evidence.ps1`   | U+2014 in Kommentar + Write-Host     |
| `scripts/dev_up.ps1`                     | `-Help`, Beispiel `pnpm dev:up:help` |
| `scripts/compose_up.ps1`                 | `-Help`                              |
| `scripts/verify_powershell_syntax.ps1`   | **neu**                              |
| `package.json`                           | `ps:verify-syntax`, `dev:up:help`    |

**Geprüfte Kette (dot-sourcen `_dev_compose.ps1`):**  
`rc_health.ps1`, `dev_up.ps1`, `compose_up.ps1`, `dev_down.ps1`, `dev_logs.ps1`, `dev_status.ps1`, `dev_reset_db.ps1`, `collect_release_evidence.ps1` — alle laden dieselbe Bibliothek; Fix zentral in `_dev_compose.ps1` + konsistente ASCII-Strings in den übrigen Skripten.

**`bootstrap_stack.ps1`:** nutzt **`Import-DotEnvFile` mit `-Encoding UTF8`** für `.env` (bereits vorhanden); finaler Schritt **`bash scripts/healthcheck.sh`** — wenn **kein** Git-Bash: Warnung und manueller Check (siehe §5).

---

## 3. Offiziell unterstützte Windows-Pfade (pnpm / PowerShell)

| Befehl                          | Skript                                         | Voraussetzung                                                  | Erwartung bei fehlendem Stack                                        |
| ------------------------------- | ---------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------- |
| `pnpm ps:verify-syntax`         | `verify_powershell_syntax.ps1`                 | nur PowerShell                                                 | **Exit 0** — kein ParserError                                        |
| `pnpm dev:up:help`              | `dev_up.ps1 -Help`                             | —                                                              | **Exit 0** — Kurzsyntax Get-Help                                     |
| `pnpm dev:up`                   | `dev_up.ps1`                                   | `.env.local`, Docker                                           | Startet Compose + Health-Warten                                      |
| `pnpm smoke` / `pnpm rc:health` | `rc_health.ps1` → Python `rc_health_runner.py` | `.env.local`, Gateway ideal                                    | **Kein** ParserError; ohne Gateway **Exit 1** (Retry/WinError 10061) |
| `pnpm stack:check`              | `check_local_edge.ps1`                         | —                                                              | HTTP-Probes; ohne Dienste **Exit 1**                                 |
| `pnpm stack:up`                 | `compose_up.ps1`                               | wie `dev:up` (ohne Browser/Smoke-Optionen wie dev_up)          | Compose + Wait                                                       |
| `pnpm bootstrap:local`          | `bootstrap_stack.ps1 local`                    | Profil-ENV, Docker, optional **Git-Bash** für `healthcheck.sh` | Stufen-Start                                                         |

**Empfohlene Reihenfolge nach frischem Clone:**

1. `pnpm ps:verify-syntax`
2. `.env.local` aus Vorlage (siehe `docs/LOCAL_START_MINIMUM.md`)
3. `pnpm dev:up` oder `pnpm bootstrap:local`
4. `pnpm smoke` oder `pnpm stack:check`

---

## 4. Regression-Prüfung (künftig)

```powershell
pnpm ps:verify-syntax
```

Optional in CI (wenn gewünscht): denselben Aufruf als eigener Schritt auf `windows-latest` — hier **nicht** eingebaut, nur dokumentiert.

---

## 5. Bash / WSL (bewusst sekundär)

- **`bootstrap_stack.ps1`** ruft am Ende **`bash scripts/healthcheck.sh`** auf (Git for Windows oder `bash` im PATH). Ohne Bash: **Warnung**, kein Abbruch des restlichen Bootstrap (siehe Skript Zeilen ~317–318).
- Für **reine** Edge-Smokes unter Windows ohne Bash: **`pnpm smoke`** (Python) und **`pnpm stack:check`** (PowerShell `Invoke-WebRequest`).
- Vollständiger **Linux/CI-Pfad** bleibt `bash scripts/healthcheck.sh` laut `docs/compose_runtime.md`.

---

## 6. Rohe Vorher-/Nachher-Outputs (Nachweis)

### 6.1 VORHER (Zustand wie in Handoff 09 — `pnpm smoke`)

```text
In ...\scripts\_dev_compose.ps1:37 Zeichen:43
+         throw "Env-Datei fehlt: $full ?" bitte .env.local.example na ...
+                                           ~~~~~
Unerwartetes Token "bitte" in Ausdruck oder Anweisung.
ParserError
 ELIFECYCLE  Command failed with exit code 1.
```

### 6.2 NACHHER — `pnpm ps:verify-syntax` (Exit 0)

```text
> bitget-btc-ai@0.1.0 ps:verify-syntax
> powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_powershell_syntax.ps1

OK: _dev_compose.ps1
OK: bootstrap_stack.ps1
OK: check_local_edge.ps1
OK: close_local_monitor_alerts.ps1
OK: collect_release_evidence.ps1
OK: compose_up.ps1
OK: dev_down.ps1
OK: dev_logs.ps1
OK: dev_reset_db.ps1
OK: dev_status.ps1
OK: dev_up.ps1
OK: docker-path.ps1
OK: rc_health.ps1
OK: rebuild_gateway.ps1
OK: release_gate.ps1
OK: start_local.ps1
OK: start_production.ps1
OK: start_shadow.ps1
OK: verify_powershell_syntax.ps1

Alle 19 PowerShell-Dateien in scripts/ sind syntaktisch gueltig.
```

### 6.3 NACHHER — `pnpm dev:up:help` (Exit 0, Auszug)

```text
> bitget-btc-ai@0.1.0 dev:up:help
> powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev_up.ps1 -Help

dev_up.ps1 [[-EnvFile] <string>] [[-ComposeFile] <string>] ... [-Help]
```

### 6.4 NACHHER — `pnpm smoke` ohne laufendes Gateway (Exit 1, **ohne** ParserError)

```text
> bitget-btc-ai@0.1.0 smoke
> powershell -NoProfile -ExecutionPolicy Bypass -File scripts/rc_health.ps1

rc_health_runner: API_GATEWAY_URL=http://127.0.0.1:8000 DASHBOARD_URL=http://localhost:3000
RETRY rc_health_edge 1/6 in 3s ... (FAIL http://127.0.0.1:8000/v1/meta/surface -> <urlopen error [WinError 10061] ...>)
...
=== SMOKE / rc_health - DIAGNOSE (letzter Fehler) ===
  FAIL http://127.0.0.1:8000/v1/meta/surface -> ...
 ELIFECYCLE  Command failed with exit code 1.
```

**Interpretation:** PowerShell- und Import-Kette **OK**; Exit 1 = **erwartbar**, wenn **kein** API-Gateway auf `:8000` lauscht.

### 6.5 NACHHER — `pnpm stack:check` ohne Stack (Exit 1, **ohne** ParserError)

```text
==> API-Gateway /health
    http://127.0.0.1:8000/health
    FEHL: Die Verbindung mit dem Remoteserver kann nicht hergestellt werden.
...
 ELIFECYCLE  Command failed with exit code 1.
```

---

## 7. Direktaufruf (optional)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/rc_health.ps1
```

Gleiches Verhalten wie `pnpm smoke`.

---

## 8. Pfad-Index

| Thema                   | Pfad                                                          |
| ----------------------- | ------------------------------------------------------------- |
| Ursprungsbefund         | `docs/chatgpt_handoff/09_LIVE_NACHWEISE_TESTS_UND_BEWEISE.md` |
| Compose-Hilfsbibliothek | `scripts/_dev_compose.ps1`                                    |
| Syntax-Regression       | `scripts/verify_powershell_syntax.ps1`                        |
| Master-Plan             | `docs/cursor_execution/00_master_execution_plan.md`           |

---

_Ende der Datei._
