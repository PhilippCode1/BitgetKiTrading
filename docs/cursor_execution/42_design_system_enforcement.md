# Task 42 — Designsystem-Durchsetzung (Komponenten & Tokens)

## Bezug

- `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md` — Konsistenz, weniger Ad-hoc-Muster.
- `docs/DESIGN_SYSTEM_MODUL_MATE.md` — Karten, Status, Buttons, Hinweise, eine Hauptaktion pro Bereich.

## Ziel dieses Schritts

**Gemeinsame UI-Sprache** durch:

1. **Einen** zentralen Block für produktive Status-/Fehlerhinweise (`ConsoleFetchNotice`) statt kopierter `div.console-fetch-notice`-Strukturen.
2. **Wiederverwendbare Hüllen** für Karten (`ContentPanel`) und Toolbar-Pills (`StatusPillLink`).
3. **Gateway-Lesehinweise** visuell an dieselbe Notice-Sprache angeglichen (`GatewayReadNotice`).

Großflächige Refactors aller `panel`-Duplikate und aller Tabellen bleiben **[FUTURE]** (Audit 07: Signaldetail, Filter-Labels).

## Kernkomponenten (neu oder bereinigt)

| Komponente               | Pfad                                        | Rolle                                                                                                                                                                                                   |
| ------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **ConsoleFetchNotice**   | `components/console/ConsoleFetchNotice.tsx` | Titel (`title` / `titlePrefix`), Body, Refresh (`refreshHint` / `refreshExtra`), optionale **Kinder** (z. B. Listen), Diagnose-`<details>`, **Schnellaktionen** mit `Suspense`, optional `wrapActions`. |
| **PanelDataIssue**       | gleiche Datei                               | Unveränderte API: übersetzt Rohfehler → `ConsoleFetchNotice`.                                                                                                                                           |
| **ContentPanel**         | `components/ui/ContentPanel.tsx`            | Semantische Hülle `section                                                                                                                                                                              | div`+ Klasse`panel`(Radius, Innenabstand laut`globals.css`). |
| **StatusPillLink**       | `components/ui/StatusPillLink.tsx`          | `Next/Link` + `status-pill` + `textDecoration: none` — Toolbar-Sprache Live-Terminal.                                                                                                                   |
| **DemoDataNoticeBanner** | `components/live/DemoDataNoticeBanner.tsx`  | Nutzt `ConsoleFetchNotice` + `console-fetch-notice__list` statt manueller Verschachtelung.                                                                                                              |
| **GatewayReadNotice**    | `components/console/GatewayReadNotice.tsx`  | Degradiert/leer: `console-fetch-notice--soft` + `__title` / `__body` statt isolierter `muted`-Blöcke.                                                                                                   |
| **LiveTerminalClient**   | `components/live/LiveTerminalClient.tsx`    | Fetch-Fehler → `ConsoleFetchNotice`; Ops/Signals/Health/Broker-Links → `StatusPillLink`.                                                                                                                |
| **EmptyStateHelp**       | `components/help/EmptyStateHelp.tsx`        | Kartenhülle über `ContentPanel` + Modifikator `empty-state-help` (Leerzustände wie Designsystem).                                                                                                       |

## CSS-Tokens / Klassen

- `.console-fetch-notice`, Modifikatoren `--soft` / `--alert` (bestehend).
- **Neu:** `.console-fetch-notice__list` — Listen in Notices; `.gateway-read-notice` — unterer Außenabstand.

## Nachweise

### Typen

```bash
pnpm check-types
```

### Komponententests

```bash
cd apps/dashboard
pnpm exec jest src/components/console/__tests__/ConsoleFetchNotice.test.tsx
pnpm exec jest src/components/layout/__tests__/SidebarNav.test.tsx
```

(`SidebarNav` bleibt IA-Regressionsschutz aus Task 41.)

### Visuelle Vereinheitlichung (ohne Screenshot-Pipeline)

| Fläche                                 | Vorher                                         | Nachher                                                     |
| -------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| Live-Terminal Fetch-Fehler             | Inline-`div` + manuelle `details`              | `ConsoleFetchNotice` (gleiche Klassen wie `PanelDataIssue`) |
| Demo-Daten-Banner                      | Eigener `div`-Aufbau                           | `ConsoleFetchNotice` + Kinderliste                          |
| Gateway degradiert (Paper/Live-Broker) | `degradation-inline` / schlichter Text         | `console-fetch-notice--soft`                                |
| Hilfe-Hub `/console/help`              | `section.panel`                                | `ContentPanel`                                              |
| Terminal-Toolbar-Links                 | Vier mal `Link` + `status-pill` + inline style | `StatusPillLink`                                            |
| Leerzustände (`EmptyStateHelp`)        | `div.empty-state-help.panel`                   | `ContentPanel` + `empty-state-help`                         |

Echte Browser-Screenshots: **[FUTURE]** unter `docs/Cursor/assets/screenshots/` (siehe Audit 07).

## [FUTURE]

- Weitere Seiten: inline `console-fetch-notice`-Markup durch `ConsoleFetchNotice` ersetzen (signals, ops, usage, …).
- `EmptyStateHelp`: Aktionsleiste mit Notice-Actions weiter teilen (optional `NoticeActionRow`).
- Tabellen: gemeinsamer `ConsoleTable`-Wrapper mit `table-wrap` + Mobile-Karten (Designsystem).

## [TECHNICAL_DEBT]

- `HelpHint`-Dialog-Button bleibt `public-btn primary` — bewusst konsistent mit bestehendem Muster; kein generisches `UiButton` in diesem Schritt.
