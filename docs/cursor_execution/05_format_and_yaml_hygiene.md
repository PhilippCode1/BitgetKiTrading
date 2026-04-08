# Format- und YAML-Hygiene

Stand: 2026-04-05

## Ziel

- GitHub Actions `ci.yml` ist **syntaktisch gültiges YAML** und wird von Prettier ohne `SyntaxError` verarbeitet.
- `pnpm format:check` ist **grün** für alle von Prettier berücksichtigten Dateien.
- Keine „Baustellen“ durch versehentliche Tool-Artefakte im Wurzelverzeichnis; Ausnahmen sind **explizit** in `.prettierignore` / `.gitignore` dokumentiert.

## 1. CI-YAML: Ursache und Fix

**Symptom:** Prettier meldete z. B. `Nested mappings are not allowed in compact mappings` bei Zeile mit dem Step-Namen `Install packages (gepinnt: requirements-dev + editables)`.

**Ursache:** In YAML ist `:` innerhalb eines **ungequoteten** Skalars nach einem Wort (`gepinnt:`) als Beginn eines eingebetteten Mappings interpretierbar — der Parser gerät aus dem Tritt, obwohl GitHub Actions den String nur als Anzeigename braucht.

**Fix:**

- Step-Namen mit Doppelpunkt im Freitext in **doppelte Anführungszeichen** setzen, z. B.  
  `name: "Install packages (gepinnt: requirements-dev + editables)"`
- Analog für `Playwright Release-Gate (… Dashboard :3000)`, damit `:3000` nicht als YAML-Sonderfall missverstanden wird.

**Prüfung:** `yaml.safe_load` (PyYAML) auf `.github/workflows/ci.yml` und `pnpm exec prettier --check .github/workflows/ci.yml`.

## 2. Repo-Format: Strategie

- Einmaliges **`pnpm exec prettier --write .`** (Root-`package.json`: `format`), damit Markdown, JSON, YAML, TS/TSX, JS, CSS usw. dem **`prettier.config.cjs`** entsprechen (`semi: true`, `singleQuote: false`, `trailingComma: "all"`).
- **Bewusst mitformatiert:** u. a. `docs/**`, `shared/contracts/**/*.json`, `infra/observability/**/*.yml`, Root-READMEs — das sind **Quell- und Vertragsartefakte im Repo**, keine flüchtigen Build-Outputs. Einheitliche Formatierung reduziert Diff-Rauschen und Review-Kosten.
- **Nicht unter den Teppich:** Keine großflächige `.prettierignore`-Erweiterung nur um `format:check` künstlich grün zu machen, ohne die Dateien zu ordnen.

## 3. `.prettierignore` — bestehende und neue Ausnahmen

| Eintrag             | Begründung                                                              |
| ------------------- | ----------------------------------------------------------------------- |
| `node_modules` etc. | Standard: Abhängigkeiten und Caches.                                    |
| `pnpm-lock.yaml`    | Lockfile — von pnpm verwaltet, nicht manuell formatieren.               |
| `**/*.tsbuildinfo`  | Incremental-Build-Cache; kein reviewbares Format.                       |
| `.env production/`  | Falscher Ordnername (Leerzeichen); gehört nicht ins Repo (siehe unten). |

Bereits vorhandene Einträge (`.turbo`, `coverage`, `build`, …) bleiben unverändert sinnvoll.

## 4. Versehentlicher Ordner `.env production/`

- Am Rechner lag ein Verzeichnis **`.env production`** (Leerzeichen) mit pnpm-ähnlichen Dateien — typisch für einen **falschen Pfad** neben dem echten Profil **`.env.production`**.
- **Entfernt** aus dem Arbeitsbaum (nicht versionieren).
- **`.gitignore`:** `/.env production/` ergänzt, damit der Ordner bei erneuter Fehleingabe nicht committed wird.
- **`.prettierignore`:** gleicher Pfad, falls der Ordner lokal wieder entsteht.

## 5. Befehle (Nachweis)

```bash
pnpm format:check
pnpm exec prettier --check .github/workflows/ci.yml
# optional nach Änderungen:
pnpm format
```

## 6. Offene Punkte

- Keine: `pnpm format:check` grün; CI-YAML von PyYAML und Prettier akzeptiert.
