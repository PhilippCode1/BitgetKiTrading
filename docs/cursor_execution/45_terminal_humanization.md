# 45 — Live-Terminal: menschliche Statussprache & klare Zustände

**Bezug:** `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md` (Terminal-Begriffe), `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md` (HTTP-Aggregat, optional Echtzeit, Teilstrecken).

**Ziel:** Nutzer erkennen schnell **Echtzeit vs. Abfrage**, **frisch vs. verzögert vs. gestört** und **fehlende Teilstrecken** — ohne dass **SSE** oder **Ingest** die Primärsprache sind. Technik bleibt über `?diagnostic=1`, Tooltips und Diagnosekarten erreichbar.

**Datum:** 2026-04-05.

---

## 1. Inhaltliche Änderungen (Kurz)

| Bereich                 | Änderung                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Toolbar**             | Drei Zeilen: Navigation/Links → Symbol & Toggles → **Statuszeile** (Historie, Puffer, Aktualisierung, Frische) + **„Daten aktualisieren“**                   |
| **Stream / Transport**  | Kurztexte: „Echtzeit aktiv“, „Abfrage alle … s“; Hinweiszeilen mit eigener, dezenter Kachel (`live-terminal-transport-note`)                                 |
| **Frische-Banner**      | Semantische Klassen: **verzögert** (blau), **kritisch** (rot), **Info** (grau) statt einheitlichem Warn-Banner                                               |
| **Leer-/Servermeldung** | `live-terminal-banner--info` statt generischem Warn-Look                                                                                                     |
| **Lineage**             | Titel **„Woher kommen die Marktdaten?“** + einleitender Satz (`live.lineage.lead`); Zusammenfassung „X von Y Strecken mit Daten“; „fehlt“ statt „Lücke“ (DE) |
| **Chart-Einstieg**      | Kurzcaption unter dem Titelblock: Kerzen = Historie, Frische = Statuszeile                                                                                   |
| **Hilfe / Leerzustand** | `help.liveTerminal`, `help.liveEmpty` an neue Begriffe angepasst                                                                                             |

---

## 2. Beispielzustände (für UI-Nachweise)

| Zustand                   | Erwartung in der UI                                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Normal**                | Statuspillen grün/gelb je nach DB/Redis; „Aktualisierung: Echtzeit aktiv“; kein Frische-Banner bei `live`                         |
| **Echtzeit aus, Polling** | Violett/blasse Transport-Notiz; Aktualisierung-Pille gelb; Text ohne Gateway-Akronyme im Fließtext                                |
| **Verzögert**             | Frische-Pille gelb; Banner **blau** („leicht verzögert“)                                                                          |
| **Veraltet / tot**        | Frische-Pille rot; Banner **rot**; klare Warnung, Chart nicht als Live werten                                                     |
| **Fetch-Fehler**          | Bestehendes `ConsoleFetchNotice` + Schnellaktionen; zusätzlich **„Daten aktualisieren“** in der Statuszeile nach Erholung nutzbar |
| **Lineage mit Lücken**    | Panel standardmäßig aufgeklappt; rote „fehlt“-Markierung an Einträgen ohne Daten                                                  |

**Screenshots (manuell ablegen):** z. B. unter `docs/Cursor/assets/screenshots/`

- `terminal-45-ok.png` — Echtzeit + grüne Pills
- `terminal-45-polling.png` — Transport-Hinweis + gelbe Aktualisierung
- `terminal-45-stale-banner.png` — roter/blauer Banner + Caption
- `terminal-45-lineage-gaps.png` — aufgeklapptes Lineage mit „fehlt“

---

## 3. Geänderte Dateien

| Pfad                                                          | Rolle                                                                      |
| ------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `apps/dashboard/src/messages/de.json`                         | `live.terminal.*`, `live.lineage.*`, `help.liveTerminal`, `help.liveEmpty` |
| `apps/dashboard/src/messages/en.json`                         | Parallele Keys                                                             |
| `apps/dashboard/src/components/live/LiveTerminalClient.tsx`   | Toolbar-Layout, Pill-Farben, Banner-Klassen, Reload, Chart-Caption         |
| `apps/dashboard/src/components/live/LiveDataLineagePanel.tsx` | Einleitungstext                                                            |
| `apps/dashboard/src/app/globals.css`                          | `.status-neutral`, `.live-terminal-*`, Banner-Varianten                    |

---

## 4. Automatisierte Prüfungen (2026-04-05)

| Kommando                                                                              | Ergebnis      |
| ------------------------------------------------------------------------------------- | ------------- |
| `JSON.parse` auf `de.json` / `en.json`                                                | **ok**        |
| `pnpm check-types` (Repo-Root)                                                        | **Exit 0**    |
| `pnpm test -- …/surface-diagnostic-catalog.test.ts …/user-facing-fetch-error.test.ts` | **13 passed** |

---

## 5. Offene Punkte

- **[FUTURE]** Shadow/Live-Seite nutzt eigene `pages.shadowLive.lineage*` — optional an gleiche Titel wie Terminal angleichen.
- **[TECHNICAL_DEBT]** `SurfaceDiagnosticCard` bleibt techniknah; Konsistenz mit neuer Primärsprache später prüfen.
