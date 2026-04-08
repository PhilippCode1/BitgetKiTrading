# Workspace-Skript-Vertrag (pnpm / Turbo) — bitget-btc-ai

**Stand:** 2026-04-05.  
**Ausgangslage (Beleg):** `docs/chatgpt_handoff/09_LIVE_NACHWEISE_TESTS_UND_BEWEISE.md` — dort ist dokumentiert, dass `pnpm --dir shared/ts run check-types` mit **`ERR_PNPM_NO_SCRIPT`** scheiterte, während `pnpm check-types` (Turbo) nur Pakete mit definiertem Skript anstößt. **Folge:** `shared-ts` war faktisch **nicht** per direktem `pnpm --dir` typisierbar; die Turbo-Kette wirkte „grün“ nur für das Dashboard, ohne expliziten Kontrakt für die Bibliothek.

---

## 1. Workspaces (pnpm)

Laut `pnpm-workspace.yaml`:

| Pfad             | Paketname                  |
| ---------------- | -------------------------- |
| `apps/dashboard` | `@bitget-btc-ai/dashboard` |
| `shared/ts`      | `@bitget-btc-ai/shared-ts` |

Weitere `package.json` unter `apps/*` / `shared/*` existieren derzeit **nicht**.

---

## 2. Root-Befehle (`package.json` im Repo-Root)

| Befehl                 | Was passiert            | Turbo-Task(s)                           | Anmerkung                                                                                                   |
| ---------------------- | ----------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `pnpm build`           | `turbo run build`       | `build` (+ `^build` auf Abhängigkeiten) | `shared-ts`: `build` = `check-types` (kein Artefakt-`dist`, siehe unten). `dashboard`: `next build`.        |
| `pnpm dev`             | `turbo run dev`         | `dev`                                   | Persistent, kein Cache.                                                                                     |
| `pnpm lint`            | `turbo run lint`        | `lint` (+ `^lint`)                      | **Aktuell:** in beiden Paketen = TypeScript-Check (`pnpm run check-types`). Kein ESLint im Repo — siehe §5. |
| `pnpm check-types`     | `turbo run check-types` | `check-types` (+ `^check-types`)        | **Reihenfolge:** zuerst `@bitget-btc-ai/shared-ts`, dann `@bitget-btc-ai/dashboard`.                        |
| `pnpm test`            | `turbo run test`        | `test` (+ `^build`)                     | Zuerst `shared-ts` **build** (Typcheck), dann u. a. Dashboard-**jest**.                                     |
| `pnpm format`          | `prettier --write .`    | —                                       | **Gesamtes Repo** (nicht Turbo).                                                                            |
| `pnpm format:check`    | `prettier --check .`    | —                                       | Gesamtes Repo.                                                                                              |
| `pnpm format:packages` | `turbo run format`      | `format`                                | Nur Dateien in Paketen mit `format`-Skript (`src`-Scope).                                                   |

**Nicht** über Turbo: `format` / `format:check` am Root — bewusst zentral, damit Markdown/JSON/CI-Dateien mitformatiert werden (sofern Prettier-Konfiguration das abdeckt).

---

## 3. Paket-Skripte (Kanone)

### 3.1 `@bitget-btc-ai/shared-ts` (`shared/ts/package.json`)

| Skript        | Befehl                           | Zweck                                                                                                      |
| ------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `check-types` | `tsc --noEmit -p tsconfig.json`  | Eigenständiger TS-Check der Bibliothek (`shared/ts/tsconfig.json`).                                        |
| `build`       | `pnpm run check-types`           | **Quellpaket ohne Emit:** „Build“-Gate = erfolgreicher Typcheck; erfüllt Turbolinks `^build` für Abhänger. |
| `lint`        | `pnpm run check-types`           | Gleiche Semantik wie Dashboard (TS als Lint-Ersatz bis ESLint).                                            |
| `test`        | `node -e "…"` Exit 0             | **Explizit:** keine Paket-Jest-Suite; Kontrakte werden im Dashboard mitgetestet.                           |
| `format`      | `prettier --write "src/**/*.ts"` | Paket-lokale TS-Dateien.                                                                                   |

**`shared-ts` ist nicht ausgenommen:** Es ist **eingebunden**, damit `pnpm --dir shared/ts run check-types` und die Turbo-Abhängigkeit `^check-types` / `^build` reproduzierbar sind.

### 3.2 `@bitget-btc-ai/dashboard` (`apps/dashboard/package.json`)

| Skript        | Befehl                                 | Zweck                                                                          |
| ------------- | -------------------------------------- | ------------------------------------------------------------------------------ |
| `check-types` | `tsc --noEmit`                         | Next/App-TS-Projekt (eigene `tsconfig.json`, inkl. Pfad-Alias zu `shared/ts`). |
| `lint`        | `pnpm run check-types`                 | Eine Definition, kein zweites `tsc`-Kommando im Skripttext.                    |
| `build`       | `next build`                           | Produktions-Build.                                                             |
| `test`        | `jest`                                 | Unit-/Komponententests.                                                        |
| `format`      | `prettier --write "src/**/*.{ts,tsx}"` | Dashboard-Quellen.                                                             |

---

## 4. Turbo (`turbo.json`) — Task-Abhängigkeiten

| Task          | `dependsOn`    | Bedeutung                                                                     |
| ------------- | -------------- | ----------------------------------------------------------------------------- |
| `build`       | `^build`       | Abhängigkeiten bauen (bei `shared-ts` = Typcheck) vor dem eigenen Build.      |
| `lint`        | `^lint`        | Abhängigkeiten zuerst linten (= deren `check-types`).                         |
| `check-types` | `^check-types` | Abhängigkeiten zuerst typisieren.                                             |
| `test`        | `^build`       | Abhängigkeiten „bauen“ (bei `shared-ts` wieder Typcheck), bevor Tests laufen. |
| `format`      | —              | Keine Topologie-Abhängigkeit; `cache: false`.                                 |
| `dev`         | —              | Persistent, kein Cache.                                                       |

**Keine toten Turbo-Äste für `check-types`:** Beide Workspace-Pakete definieren `check-types`; Turbo führt sie in korrekter Reihenfolge aus.

---

## 5. Bewusste Entscheidungen / technische Schuld

1. **`lint` = TypeScript:** Es gibt **kein** ESLint in den Paketen. `lint` und `check-types` sind inhaltlich gleich (Dashboard/ shared-ts), aber **getrennte Turbo-Tasks**, damit `pnpm lint` und `pnpm check-types` weiterhin beide sinnvoll adressierbar sind. Doppelte `tsc`-Laufzeit, wenn beide nacheinander aufgerufen werden — akzeptiert bis ESLint eingeführt wird.
2. **`shared-ts` ohne `dist`:** Verbraucher (Dashboard) binden über `workspace:*` und Pfad/Resolution die **Quell-**`.ts`-Dateien; `build` erzeugt keine Dateiausgabe.
3. **Root `format` vs. `format:packages`:** Root formatiert das **gesamte** Repository; `format:packages` nur Pakete mit eigenem `format`-Skript.

---

## 6. Verifikationsläufe (Rohauszüge, 2026-04-05)

### 6.1 `pnpm --dir shared/ts run check-types` — **Exit 0**

```text
> @bitget-btc-ai/shared-ts@0.1.0 check-types
> tsc --noEmit -p tsconfig.json
```

### 6.2 `pnpm check-types` (Turbo) — **Exit 1** (nur Dashboard-TS-Fehler, bekannt)

```text
• Running check-types in 2 packages
@bitget-btc-ai/shared-ts:check-types: > tsc --noEmit -p tsconfig.json
@bitget-btc-ai/dashboard:check-types: > tsc --noEmit
@bitget-btc-ai/dashboard:check-types: error TS2339 ... admin/page.tsx
@bitget-btc-ai/dashboard:check-types: error TS2322 ... paper/page.tsx
 Tasks:    1 successful, 2 total
Failed:    @bitget-btc-ai/dashboard#check-types
```

**Interpretation:** Die Pipeline ist **logisch**: `shared-ts` ist grün; das Monorepo scheitert transparent an **Dashboard**-Typfehlern (nicht an fehlenden Skripten).

### 6.3 `pnpm --dir apps/dashboard run check-types`

Gleiche TS-Fehler wie in 6.2 — **Exit 1**.

### 6.4 `pnpm test` (Turbo)

`shared-ts:test` und `shared-ts:build` laufen; Dashboard-`jest` kann weiterhin an einzelnen Specs scheitern (z. B. `SidebarNav`) — das ist **Testlogik**, nicht Workspace-Konfiguration. Der Root-Befehl `test` ist damit **definiert** und reproduzierbar.

---

## 7. Kurz-Checkliste für Entwickler

1. Nur Shared-Bibliothek typisieren: `pnpm --dir shared/ts run check-types`
2. Gesamtes TS laut Abhängigkeitsgraph: `pnpm check-types`
3. Nach Shared-Änderungen vor Dashboard-Build: Turbo erzwingt `^build` / `^check-types` automatisch.
4. Repo-weites Format: `pnpm format`
5. Nur Paket-Quellen: `pnpm format:packages`

---

## 8. Pfad-Index

| Datei                                                         |
| ------------------------------------------------------------- |
| `package.json` (Root)                                         |
| `pnpm-workspace.yaml`                                         |
| `turbo.json`                                                  |
| `apps/dashboard/package.json`                                 |
| `shared/ts/package.json`                                      |
| `shared/ts/tsconfig.json`                                     |
| `docs/chatgpt_handoff/09_LIVE_NACHWEISE_TESTS_UND_BEWEISE.md` |

---

_Ende der Datei._
