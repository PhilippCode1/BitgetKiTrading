# Sauberes Release-Artefakt (ohne Ballast)

Ziel: reproduzierbarer Build und kleine Docker-Kontexte — **keine** lokalen Caches, Coverage, Logs, `.next`-Buildreste, virtuelle Environments oder Workspace-`node_modules` im Image bzw. im gepackten Quell-Tarball.

## Node / Dashboard (Monorepo)

1. Frisches Arbeitsverzeichnis oder `git clean` (siehe unten).
2. **pnpm** wie in Root-`package.json` (`packageManager`-Feld), z. B. via Corepack: `corepack enable && corepack prepare pnpm@10.30.1 --activate`.
3. Abhaengigkeiten: `pnpm install --frozen-lockfile` (Release) bzw. `pnpm install` (Entwicklung mit Lockfile-Update).
4. Dashboard-Produktion: `pnpm --dir apps/dashboard run build` (Output jetzt unter `apps/dashboard/build` mit `output: standalone`).
5. Produktion starten: `pnpm --dir apps/dashboard start` startet den Standalone-Server (`node build/standalone/apps/dashboard/server.js`) statt `next start`.
6. Docker-Image Dashboard: Build aus Repo-Root mit `apps/dashboard/Dockerfile`; der Runner kopiert nur das Standalone-Artefakt und keine Workspace-`node_modules`.

## Python-Services

1. Interpreter **3.11**; CI nutzt eine feste Patch-Version (Workflow `python-version`).
2. Gemeinsame Dev-/CI-Toolchain: `python -m pip install -r requirements-dev.txt` (gepinnte Versionen).
3. Pakete pro Service: `pip install -c constraints-runtime.txt -e ./services/<name>` wie in CI; die Datei `constraints-runtime.txt` pinnt den gemeinsam genutzten Laufzeitkern.
4. Service-Images: `docker build` im Service-Verzeichnis; Python-Dockerfiles nutzen `constraints-runtime.txt`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` und einen non-root-User.

## Git-Artefakt (Source-Release)

Vor dem Erzeugen eines Source-Bundles (ohne `.git`):

- `.gitignore` schliesst u. a. aus: `node_modules/`, `.next/`, `build/`, `.turbo/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`/`venv/`, Coverage-Dateien, `artifacts/backtests/*` (außer `.gitkeep`), Logs.
- Pruefung: `git clean -fdX` **nur** nach Verifizierung — entfernt ignorierte Dateien im Working Tree.

## CI-Spiegel

- Python: `.github/workflows/ci.yml` — `pip install -r requirements-dev.txt` + editable installs + pytest/coverage.
- Dashboard: gleicher Workflow — `pnpm install --frozen-lockfile` + Dashboard lint + `test:ci` + Build.

Keine parallelen Lockfiles fuer das Dashboard: **nur** `pnpm-lock.yaml` am Root.

## Release-Candidate

- Repo-weit gebuendelter RC-Lauf: `bash scripts/release_candidate.sh`
- Der RC-Pfad erzwingt u. a. `release_sanity_checks.py --strict`, Python-Coverage-Gates, Schema-Check, blocking `pip-audit`, Dashboard-`test:ci`, Build, `pnpm audit` und Compose-Config-Validierung.
