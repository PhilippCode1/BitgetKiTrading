# Task 41 — Informationsarchitektur: einfache Ansicht vs. Profi-Konsole

## Ziel

Endkundinnen sehen **weniger Menülärm** und **schnellere Pfade** zu Chart, **KI & Systemstatus**, **Paper**, **Konto**, **Hilfe** und Orientierung — mit **dieselben i18n-Keys und Layout-Patterns** wie die Profi-Konsole (`DashboardShell`, `SidebarNav`, `HelpHint`, Kacheln). Operatoren behalten **alle Tiefe**, aber mit **klarerer Gruppierung** (Health beim Cockpit, weniger überlappende Sektionen auf der Startseite).

**Grundlage:** `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md` (Simple vs. Pro, Navigationsstruktur, einheitliche Sprachlogik).

## Informationsarchitektur (neu)

### Einfache Ansicht — Sidebar (`SidebarNav`, `uiMode="simple"`)

```
Start
— Schnellzugriff
    KI & Systemstatus   → /console/health
    Üben (Paper)        → /console/paper
    Mein Konto          → /console/account
— Markt & Entscheidungen
    Chart & Markt       → /console/terminal
    Signale             → /console/signals
— Hilfe & Orientierung
    Hilfe & Überblick   → /console/help   [neu]
    Erste Schritte      → /onboarding?…
    Sprache & Einstellungen → /console/account/language
```

### Profi-Konsole — Sidebar (`uiMode="pro"`)

```
Übersicht
— Cockpit, Freigaben & System        [Überschrift angepasst]
    Operator Cockpit, Terminal, Freigaben, Health & Incidents
— Markt & Signale
    Universum, Matrix, Signal-Center, No-Trade
— Ausführung
    Live-Broker, Shadow vs. Live, Paper
— Model & Learning
    Learning & Drift, Strategien
— News, Plan & Integrationen         [Health hier entfernt]
    News, Kosten & Plan, Integrations-Check
— Konto & Verbrauch
    Mein Konto
[+ Intern: Admin bei Berechtigung]
```

### Konsole-Start (`/console`)

- **Simple:** Kacheln in Reihenfolge Chart (primär) → KI → Paper → Konto → Signale → **Hilfe & Überblick** → Sprache.
- **Pro:** Fünf Kachelbereiche statt sechs überlappender: (1) Markt inkl. Signale, (2) Ausführung inkl. Cockpit/Health/Paper, (3) Modelle, (4) News/Usage/Integrationen, (5) Konto + Tour + **Hilfe-Hub**.

### Neue Route

| Pfad            | Zweck                                                                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/console/help` | Kuratierte Sprungliste (Chart, Signale, KI, Paper, Konto, Einstellungen, Tour, Start) — **kein** zweites Designsystem, nur `Header` + `panel` + Links. |

## Hauptflüsse (Endkunde)

1. **Nach Login:** Simple-Modus (Cookie `dashboard_ui_mode`, siehe `dashboard-prefs`) → Sidebar „Schnellzugriff“ zuerst mit KI/Paper/Konto.
2. **KI-Frage:** Sidebar oder Start-Kachel → `/console/health`.
3. **Orientierung verloren:** `/console/help` oder „Hilfe & Überblick“-Kachel.
4. **Tiefer gehen:** `UiModeSwitcher` → „Alle Funktionen (Pro)“.

## Nachweise

### UI-Navigation (automatisiert)

`SidebarNav.test.tsx` prüft u. a.:

- Pro: Link **Health & incidents** liegt in der **Cockpit**-Sektion; **Integration check** in **News, plan & integrations**; Health **nicht** doppelt in der unteren Sektion.
- Simple: Sektion **Quick access** mit Reihenfolge KI → Paper → Konto; Link **Help & overview** mit `href="/console/help"`; kein Operator-Cockpit.

**Befehl:**

```bash
cd apps/dashboard
pnpm exec jest src/components/layout/__tests__/SidebarNav.test.tsx
```

**Ergebnis (Referenz):** 4 Tests grün (Stand Umsetzung Task 41).

### Routing

- Next.js App Router: `src/app/(operator)/console/help/page.tsx` → öffentliche URL `/console/help` innerhalb des bestehenden `(operator)`-Layouts.
- Breadcrumbs: `ConsoleBreadcrumbs` mappt Segment `help` → `pages.consoleHelp.breadcrumb`; `integrations` → `console.nav.integrations`.

### Screenshots / visueller Nachweis

Im Repo liegt unter `docs/Cursor/assets/screenshots/` derzeit kein Release-Screenshot-Set (siehe Audit 07). **Ersatz:** die obigen Jest-Tests rendern die Sidebar im DOM und prüfen **sichtbare Link-Bezeichnungen** und **Ziel-URLs** — das ist ein **Render-Nachweis** der Hauptnavigation ohne Browser-Pipeline.

**Manuell (optional):** Dashboard starten, Simple/Pro umschalten, Sidebar mit obigen ASCII-Bäumen abgleichen.

## Konsistenz Simple / Pro

- Gleiche Komponenten: `DashboardShell`, `SidebarNav`, `UiModeSwitcher`, `LocaleSwitcher`, `HelpHint`.
- Gleiche Token/Klassen: `dash-sidebar`, `dash-nav`, `console-tile`, `panel`.
- Texte nur über `de.json` / `en.json` (neu: `simple.nav.*`, `pages.consoleHelp.*`, `consoleHome.simple.tileHelp`, `consoleHome.pro.integ`, `consoleHome.pro.helpHub`, angepasste `console.navSections.*`).

## [FUTURE]

- Echte Screenshot-Pipeline (z. B. Playwright) unter `docs/Cursor/assets/screenshots/` mit Datum.
- Hilfe-Hub um kontextsensitive FAQ-Keys erweitern, ohne Roh-API-Begriffe (Audit 07).

## [RISK]

Nutzer mit Lesezeichen auf alte „Health nur unter Betrieb“-Erwartung: URL `/console/health` unverändert; nur Menüposition wechselt.
