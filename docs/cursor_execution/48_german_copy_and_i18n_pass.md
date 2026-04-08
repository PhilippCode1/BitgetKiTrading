# Lauf 48: Deutsche Oberflächentexte, i18n und EN-Parität

Stand: 2026-04-05

## Bezug „Datei 07“

- **`docs/cursor_execution/07_ci_and_release_contract.md`**: Qualitätsleiste inkl. `pnpm check-types` für Dashboard und shared-ts (Turbo).
- **`docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md`**: Audit zu Mischsprache, Rohfeldnamen (z. B. Signaldetail, Filter-Hints) und fehlender i18n — dieser Lauf adressiert einen Teil davon gezielt.

## Ziel des Laufs

- Sichtbare Texte stärker in **`de.json` / `en.json`** bündeln, DE-Copy natürlicher und ohne Roh-API-Labels in ausgewählten Flächen.
- Englische Parallele ergänzen, wo sie fehlte (**`live.paperPanel`**, **`live.signalPanel`**, **`live.newsPanel`** in `en.json`).
- Signaldetail-Technikblock: Beschriftungen über **`pages.signalsDetail.techFields.*`** statt Feldnamen im JSX.
- Health-Raster: **`pages.health.grid.*`** statt durchgängig englischer/deutsch-englischer Mischlabels in `HealthGrid`.
- Live-Terminal-Seitenleiste: **`SignalPanel`**, **`PaperPanel`**, **`NewsPanel`** an bestehende/neue `live.*`-Keys anbinden.
- Strategie-Detail: Metadaten-Labels und Roh-JSON-Klapptext über **`pages.strategiesDetail.scope*`**.
- Strategien-Tabelle: Spalten- und Kartenbeschriftungen aus **`pages.strategiesList.*`**.

## Prüfnachweise (ausgeführt)

### Hartcodierte Strings im Dashboard (Stichprobe / Suche)

- Bearbeitete TSX-Dateien wurden auf zentrale Nutzerstrings geprüft und auf Message-Keys umgestellt (siehe „Betroffene Pfade“).
- Es verbleiben bewusst dichte Operator-Seiten mit vielen Tabellenüberschriften (z. B. **`apps/dashboard/src/app/(operator)/console/ops/page.tsx`**) — nicht Gegenstand dieses Laufs.
- Empfohlene Wiederholungssuche (PowerShell, Ausschnitt):

```powershell
Set-Location apps/dashboard/src
Get-ChildItem -Recurse -Filter *.tsx |
  Where-Object { $_.FullName -notmatch '\\__tests__\\' } |
  Select-String -Pattern 'className="label">[^<{]+' |
  Select-Object -First 40
```

### Typecheck

```text
pnpm check-types   → erfolgreich (Turbo: dashboard + shared-ts)
```

### Zentrale DE/EN-Flächen nach Bereinigung

| Bereich                    | DE-Keys (Auszug)                                                | EN-Parität                                                  |
| -------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------- |
| Health-Raster              | `pages.health.grid.*`                                           | identische Struktur                                         |
| Signaldetail Technik       | `pages.signalsDetail.techFields.*`, verbesserte `techMetrics.*` | ja                                                          |
| Live-Terminal Seitenleiste | `live.signalPanel.*`, `live.paperPanel.*`, `live.newsPanel.*`   | `signalPanel`/`paperPanel`/`newsPanel` in `en.json` ergänzt |
| Strategien-Liste           | `pages.strategiesList.mobilePfLabel`, `mobileWinLabel`, `th*`   | ja                                                          |
| Strategie-Detail Scope     | `pages.strategiesDetail.scope*`                                 | ja                                                          |

### Copy-Heuristik (optional)

```text
cd apps/dashboard
pnpm run check-locale-de
```

- Prüft **`de.json`** auf **snake_case**- und ausgewählte Intern-Tokens in **strikten** Nutzerpräfixen (`simple.*`, `welcome.*`, `live.signalPanel.*`, …).
- Vollständiger Baum (viele erwartete Ops-Hinweise): `STRICT_LOCALE_CHECK=all node ../../scripts/check_dashboard_de_copy.mjs`
- Skript: **`scripts/check_dashboard_de_copy.mjs`**
- Abgleich mit Python-Vertrag: `shared_py.design_system_contract.FORBIDDEN_USER_VISIBLE_TERMS` — dieselbe Philosophie („keine Dev-Sprache in Endnutzer-UI“), Dashboard-Skript ist eine **leichte, JSON-basierte Ergänzung**.

## Vorher → Nachher (wichtige Beispiele)

| Kontext                                  | Vorher (sinngemäß / im Code)                                                     | Nachher                                                                                                 |
| ---------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Signaldetail Technik                     | Sichtbare Labels wie `canonical_instrument_id`, `stop_fragility_0_1`             | Deutsche Bezeichnungen z. B. „Interne Instrumentenkennung“, „Stop-Anfälligkeit (0–1)“ über `techFields` |
| `techMetrics` (DE)                       | `take_trade_prob`, `trade_action`, `timeframe` als Labeltext                     | „Handelswahrscheinlichkeit (Take-Trade)“, „Handlungsvorschlag“, „Zeitrahmen“                            |
| Health `HealthGrid`                      | „Execution Controls“, „Ops Summary“, „Services“, „Redis Streams“, gemischt DE/EN | Einheitlich über `pages.health.grid.*` (DE/EN getrennt gepflegt)                                        |
| `SignalPanel`                            | Hartcodiert DE/EN-Mix („Take-Trade P“, „Exp. Return“, …)                         | `live.signalPanel.*` — EN folgt in `en.json`                                                            |
| `PaperPanel` / `NewsPanel`               | Lange DE-Texte mit Backticks/Migrations-IDs                                      | Kurze, nutzerfreundliche `live.paperPanel.empty` / `live.newsPanel.empty`                               |
| Strategie-Detail                         | `canonical_instrument_id`, `Eligibility`, `inv=` …                               | `pages.strategiesDetail.scope*` mit Satzformen und ja/nein                                              |
| Strategien-Tabelle                       | Mobile: „PF (roll.)“, Desktop-Header hardcodiert EN                              | Alles aus `pages.strategiesList.*`                                                                      |
| JSON-Zusammenfassungen Signaldetail (DE) | `instrument_metadata (JSON)`                                                     | „Instrument-Stammdaten (Roh-JSON)“                                                                      |

## Betroffene Pfade (Code)

- `apps/dashboard/src/messages/de.json`
- `apps/dashboard/src/messages/en.json`
- `apps/dashboard/src/components/signals/SignalDetailTechnicalCollapsible.tsx`
- `apps/dashboard/src/components/panels/HealthGrid.tsx`
- `apps/dashboard/src/app/(operator)/console/health/page.tsx`
- `apps/dashboard/src/components/live/SignalPanel.tsx`
- `apps/dashboard/src/components/live/PaperPanel.tsx`
- `apps/dashboard/src/components/live/NewsPanel.tsx`
- `apps/dashboard/src/components/tables/StrategiesTable.tsx`
- `apps/dashboard/src/app/(operator)/console/strategies/page.tsx`
- `apps/dashboard/src/app/(operator)/console/strategies/[id]/page.tsx`
- `scripts/check_dashboard_de_copy.mjs`
- `apps/dashboard/package.json` (Script `check-locale-de`)

## Bekannte offene Punkte

- **`ops/page.tsx`** und weitere dichte Operator-Tabellen: weiterhin viele lokale Überschriften — nächster sinnvoller Schritt wäre ein `pages.ops.table.*`-Namespace.
- **`FORBIDDEN_USER_VISIBLE_TERMS`**: automatische Spiegelung ins Dashboard-Skript ist **nicht** erfolgt (Duplikatpflege); bei Bedarf JSON-Export aus Python oder gemeinsame Liste ergänzen.
- Vollscan `STRICT_LOCALE_CHECK=all` schlägt erwartbar oft an — nur für schrittweise Bereinigung oder Audit nutzen.
