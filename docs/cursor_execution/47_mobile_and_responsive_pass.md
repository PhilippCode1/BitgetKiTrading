# 47 — Mobile- und Responsive-Pass (Konsole)

**Bezug:** `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md` (Abschnitt Mobile / Tabellen).

**Ziel:** Kernflüsse auf schmalen Viewports **bedienbar** machen: keine Tabellen als Standardlösung per horizontalem Scroll, wo eine **Kartenstapel**-Lesart sinnvoller ist; Charts und Touch-Flächen skalieren; Navigation bleibt erreichbar.

---

## Breakpoint-Entscheidungen

| Bereich                      | Grenze              | Verhalten                                                                                                                                                                                                                   |
| ---------------------------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Schmal (mobile)**          | `max-width: 720px`  | Kartenlisten (`.console-mobile-only`), Desktop-Tabellen aus (`.console-desktop-only`), weniger `dash-main`-Padding, Locale-Leiste gestapelt, Filter volle Breite, Form-Primary-Buttons min. 44px hoch und ggf. volle Breite |
| **Tablet / Sidebar-Umbruch** | `max-width: 900px`  | Sidebar oben, horizontale Nav-Links mit min. 44px Tap-Höhe, `.grid-2` einspaltig (bereits vorhanden)                                                                                                                        |
| **Terminal-Spalten**         | `max-width: 1100px` | Chart + Seitenleiste bereits einspaltig (bestehend)                                                                                                                                                                         |
| **Charts**                   | `max-width: 720px`  | `.chart-wrap` Höhe `min(52vh, 320px)`; `.equity-chart-box` kompakter                                                                                                                                                        |

CSS-Kommentar am Anfang von `globals.css` dokumentiert die drei Stufen (narrow / tablet / desktop).

---

## Zehn Nutzerflüsse — Umsetzung

| Fluss            | Mobile/tablet Maßnahme                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Navigation**   | ≤900px: Sidebar oben, Links umbrechen, `min-height: 44px` auf `.dash-nav-link`; ≤720px: Locale-Bar untereinander                                                |
| **Health**       | Alerts + Outbox: **Karten** unter 720px (Severity, Titel, Nachricht bzw. Typ/Status/Symbol/Zeit); Desktop-Tabelle unverändert; Leerzustände auch mobil sichtbar |
| **Paper**        | Offene Positionen + letzte Trades: **Karten** mit Kernfeldern; volle Tabelle nur ≥721px                                                                         |
| **Signals**      | **Karten** mit Zeit, TF, Richtung, Symbol, Entscheidung, Risiko, Ausführung, Detail-Link; breite Tabelle nur Desktop                                            |
| **Signaldetail** | Keine Tabellen-Umbauten in diesem Schritt; profitiert von globalem Padding und lesbaren Panels; **[FUTURE]** weitere Kollaps-Gruppen                            |
| **Terminal**     | Bestehendes einspaltiges Layout ≤1100px; Chart-Höhe ≤720px reduziert; Toolbar war schon mehrzeilig                                                              |
| **Live-Broker**  | Globale Filter-/Panel-Verbesserungen; breite Broker-Tabellen **[TECHNICAL_DEBT]** nächster Ausbauschritt (analog Signals/Paper)                                 |
| **Account**      | `customer-quick-grid` einspaltig ≤720px                                                                                                                         |
| **Assist**       | Panel `.form-actions`: volle Breite + min. 44px für Primary auf schmalen Screens                                                                                |
| **Settings**     | Sprache unter `/console/account/language`: gleiche Shell wie Account; Locale-Schalter 44px Touch-Ziel                                                           |

---

## Screen-Beweise (Rendernachweise)

**Automatisch:** Playwright-Spezifikation `e2e/tests/responsive-shell.spec.ts`:

- Viewports **390×844** (mobile) und **834×1112** (tablet).
- Pro Viewport: Kernpfade werden geladen (Sidebar + Main); Terminal prüft `.live-terminal-toolbar` statt `h1`.
- Optional werden PNGs nach `docs/cursor_execution/47_responsive_assets/` geschrieben (Dateinamen z. B. `mobile-_console_signals.png`), sobald `pnpm e2e` mit laufendem Dashboard und gültiger Auth ausgeführt wird.

**Manuell:** DevTools responsive Mode auf dieselben Breakpoints; Signale/Paper/Health auf Kartenansicht prüfen.

---

## Tests

| Art           | Ort                                                             |
| ------------- | --------------------------------------------------------------- |
| **UI (Jest)** | `SignalsTable.mobile.test.tsx` — Kartenliste + Tabelle im DOM   |
|               | `PaperTables.test.tsx` — Mobile-Stack bei OpenPositions         |
| **E2E**       | `e2e/tests/responsive-shell.spec.ts` — Lade-Smoke + Screenshots |
| **Typen**     | `pnpm check-types`                                              |

---

## Gemeinsame CSS-Klassen

- `.console-mobile-only` / `.console-desktop-only` — sichtbarkeit je nach 720px
- `.console-stack-list`, `.console-stack-card`, `.console-stack-card__dl`, … — einheitliche Karten
- `.signals-mobile-cards` — Signale-Liste

---

## Offene Punkte

- **[TECHNICAL_DEBT]** Live-Broker, Journal, Ledger und weitere dichte Tabellen: gleiches Kartenmuster wie Paper/Signals nachziehen.
- **[FUTURE]** Signaldetail: technische Felder in Akkordeons / zweite Spalte nur ab `min-width`.
- PNGs unter `47_responsive_assets/` werden nicht zwingend versioniert (nur `.gitkeep`); lokal nach `pnpm e2e` erzeugen für Reviews.
