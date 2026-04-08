# Frontend: UX, Sprache und Design-Audit (bitget-btc-ai)

**Zweck:** ChatGPT soll nach dem Lesen einschätzen können, wie ausgereift die Oberfläche für echte Nutzerinnen ist, wo sie noch technisch, leer oder unklar wirkt, und welche Richtung zu einer klaren, modernen, deutschsprachigen Oberfläche führt.

**Methodik:** Auswertung von `apps/dashboard` (Seiten, Komponenten, `de.json`/`en.json`), `globals.css`, Navigationslogik, Fehler-Mapping sowie Abgleich mit `docs/DESIGN_SYSTEM_MODUL_MATE.md` und `shared_py.design_system_contract`. **Keine** visuelle Screenshot-Prüfung in dieser Session — der Ordner `docs/Cursor/assets/screenshots/` enthält aktuell nur Platzhalter (`.gitkeep`).

**Kennzeichnung:** `verifiziert (Code)` = direkt im Repository belegt; `abgeleitet` = sachliche Schlussfolgerung aus Struktur und Texten; `nicht verifiziert (visuell)` = ohne Browser-/Design-Review.

---

## 1. Zusammenfassung für Entscheider

Die Oberfläche ist **funktional und in Teilen sehr durchdacht**: zweisprachig (DE/EN), zentrale Fehlertexte sind **verständlich** und meist **ohne** sichtbare HTTP-Codes, es gibt eine **einfache Ansicht** für weniger Menüpunkte, **Kontext-Hilfen** (`HelpHint`) und **ausführliche Leerzustände** in den Hilfe-Texten (z. B. Signale, Usage, Broker).

Gleichzeitig ist das Produkt **zweigleisig**: Für **Endkundinnen in der einfachen Ansicht** wirken Willkommen, Onboarding, Sprachwahl und einige Erklärtexte **eher reif**. Für **Operatorinnen in der Profi-Konsole** — besonders **Signaldetail** und stark datengetriebene Tabellen — dominiert **Fach- und Feldjargon** (englische Spaltennamen, Abkürzungen wie OOD, SSE, Meta-Lane). Das widerspricht teilweise der eigenen Designregel „keine internen Codes in der Kopfzeile“ (`DESIGN_SYSTEM_MODUL_MATE.md`).

**Kernurteil:** Die Basis für eine **moderne, vertrauensvolle** Oberfläche ist da (Layout-Tokens, Panels, i18n). Die **Sprach- und Label-Konsistenz** und die **Mobile-Tauglichkeit großer Tabellen** sind noch nicht überall auf dem Niveau, das ein zahlender Laie ohne Fachhintergrund erwarten würde.

---

## 2. Aktueller UX-Reifegrad

| Bereich                        | Einschätzung                                                                                                         | Beleg                                                                                  |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Navigation**                 | Gut strukturiert, Sektionen logisch; Simple vs. Pro ist nachvollziehbar                                              | `SidebarNav.tsx`                                                                       |
| **Fehler & Wiederherstellung** | Stark: Klassifizierung → freundliche Titel/Texte, optional Technik unter „Diagnose“, Schnellaktionen                 | `PanelDataIssue`, `translateFetchError`, `ConsoleFetchNotice`                          |
| **Leerzustände**               | Uneinheitlich: Manche Seiten mit `help.*` sehr gut; andere nur kurz „leer“                                           | `de.json` `help.*` vs. einzelne `emptyMessage`-Keys                                    |
| **Ladezustände**               | Vorhanden (Skeleton, Terminal-„wird vorbereitet“, KI-Ladezeiten mit Sekunden)                                        | `PageLoadingSkeleton`, `LiveTerminalClient`, LLM-Panels                                |
| **Tiefe / Informationsdichte** | Profi-Seiten sehr dicht; einfache Ansicht reduziert das sinnvoll                                                     | Simple-`SECTIONS`                                                                      |
| **Mobile**                     | CSS enthält Breakpoints und `max-width`-Anpassungen; **große Tabellen** bleiben fachlich riskant auf kleinen Screens | `globals.css` — `verifiziert (Code)`; echtes Tap-Testing `nicht verifiziert (visuell)` |
| **Barrierefreiheit**           | Teilweise (z. B. `aria-busy`, `role="status"` an Notices); kein vollständiges Audit                                  | `ai-architecture.md`, Komponenten                                                      |

**Gesamtnote UX (grob):** ca. **6,5–7,5 / 10** — stark bei Betriebsfehlern und geführten Flows, schwächer bei Rohdaten-Ansichten und Einsteiger-Klarheit auf Profi-Seiten.

---

## 3. Aktueller Sprach-Reifegrad

**Stärken (`verifiziert (Code)`):**

- **Hoher Anteil natürliches Deutsch** in Willkommen, Hilfe-Bausteinen, vielen Seitentiteln und Fehlermeldungen (`ui.fetchError.*`).
- **Umlaute** werden durchgängig korrekt genutzt (z. B. „Erklärung“, „Überschreitung“, „gültige“) — kein künstliches „ue“-Ersatz in den produktiven `de.json`-Flächen, die geprüft wurden.
- **Klarheit bei Risiko:** Formulierungen wie „keine Kaufempfehlung“ bei Signalen (`pages.signals.subtitle`) sind ehrlich und gut.
- **Englische Paralleldatei** `en.json` existiert — sinnvoll für internationale Operatorinnen.

**Schwächen:**

- **Filter-Labels** mischen Deutsch mit **rohen API-Feldnamen** (`market_family`, `playbook_family`, `specialist_router_id` …) — für Laien wirkt das wie ein Entwicklertool (`de.json` `pages.signals.filters`).
- **Signaldetailseite:** Viele **hart im JSX stehende** Beschriftungen sind **technische Feldnamen** (`canonical_instrument_id`, `stop_fragility_0_1`, …) oder Mischformen — das ist für einen einfachen Endkunden **nicht natürliches Deutsch**, sondern Datenlexikon (`signals/[id]/page.tsx`).
- **Live-Terminal:** Begriffe wie **SSE**, **Polling**, **Ingest** sind für Technikerinnen Standard, für Kundinnen ohne IT-Hintergrund **zu technisch** (`live.terminal` in `de.json`).
- **Designkontrakt vs. Praxis:** `FORBIDDEN_USER_VISIBLE_TERMS` verbietet u. a. „llm“, „json“ in Endnutzer-Texten — die **durchsetzung** erfolgt nicht automatisch überall in der UI; manche Texte nähren sich Fachvokabular (z. B. „Facets“, „Outbox“ in Hilfetexten — sachlich ok für Ops, weniger für „einfacher Endkunde“).

**Gesamtnote Sprache:** **6/10** für das **gesamte** Dashboard gemischt; **8/10** für die **explizit editorialisierten** Bereiche (Welcome, Help, Fetch-Errors).

---

## 4. Aktueller Design-Reifegrad

**Passung zum dokumentierten Designsystem (`verifiziert (Code)` + `DESIGN_SYSTEM_MODUL_MATE.md`):**

- **Ruhige Farbpalette**, **max. Inhaltsbreite** (~1120px), **Karten/Panels**, **dezente Schatten** — entspricht dem Konzept „seriös, nicht Crypto-Spielzeug“.
- **System-Schriftstack** ohne erzwungene Webfont-Ladung — wirkt modern-neutral.
- **Buttons:** Klassen wie `public-btn`, Varianten ghost/primary kommen vor; Hierarchie ist auf Seiten mit einem klaren Haupt-Call oft ok.

**Lücken:**

- **Tabellen:** Designziel „auf Mobile Kartenstapel“ ist **nicht** flächendeckend umgesetzt — viele Konsolen-Seiten nutzen **horizontales Scrollen** bei breiten Tabellen (`abgeleitet` aus üblichem Muster `table-wrap` / Daten-tabellen).
- **Dark Mode:** In der Doku **optional Phase 2** — im Audit-Zeitpunkt kein Pflicht-Feature.
- **Illustrationen:** Platzhalter-Regeln existieren; echte Medien sind **nicht** Teil dieses Audits.

**Gesamtnote Design:** **7/10** — wirkt konsistent und „SaaS-seriös“, aber noch **wenig emotional** und **nicht überall** auf Mobile optimiert.

---

## 5. Stärken der vorhandenen Oberfläche

1. **Zentrale Fehlerhumanisierung:** Statt roher `fetch`-Strings sehen Nutzerinnen **Titel + Erklärung + Refresh-Hinweis**; Technik nur mit `?diagnostic=1`.
2. **Hilfe-Layer:** Viele Begriffe (Modus, Sprache, Usage, Broker, Signale, Terminal) haben **Kurz + Lang** in einem Dialog — das ist **überdurchschnittlich** für interne Konsolen.
3. **Einfache Ansicht:** Reduziert kognitive Last — gute Produktentscheidung für „einfachen Endkunden“.
4. **Ehrliche Signal-Copy:** Keine verschwiegenen „KI macht Gewinn“-Versprechen in den geprüften Signal-Titeln.
5. **Live-Terminal:** Datenfluss-Panel („Teilstrecke“, „Nächster Schritt“) **entschärft leere Charts** — sehr wertvoll für Support.
6. **Zweisprachigkeit und Cookie-Sprachspeicher** sauber beschrieben (Welcome-Texte).

---

## 6. Schwächen der vorhandenen Oberfläche

1. **Signaldetail als „Schema-Browser“:** Die Seite zeigt **Dutzende Felder** mit **englischen internen Namen** — für Nicht-Expertinnen **überwältigend** und **nicht** im Sinne von `DISPLAY_RULE_*` „Alltagssprache“.
2. **Inkonsistente Internationalisierung:** Teilweise `t("…")`, teilweise **feste deutsche oder englische Strings** in TSX — würde EN-Locale **Lücken oder Mischmasch** erzeugen.
3. **Filter-UI:** Sichtbare **`market_family`**-Labels wirken wie **Debug-Ansicht**, obwohl der Rest der App sich Mühe mit Erklärungen gibt.
4. **Terminal-Terminologie:** „SSE“, „Ingest“, „Polling“ — **korrekt**, aber **nicht** endkundenfreundlich ohne Glossar.
5. **Primäraktionen:** Auf dichten Seiten mehrere Buttons gleichwertig — Hierarchie nicht überall klar (Designregel: eine Hauptaktion pro Bereich).
6. **Visuelle Prüfung fehlt:** Keine dokumentierten Screenshots aus dieser Session — Abstände auf echten Geräten **nicht verifiziert**.

---

## 7. Tabelle der wichtigsten UI-Probleme

| Problem                                          | Auswirkung                                        | betroffene Stelle (Beispiel)         |
| ------------------------------------------------ | ------------------------------------------------- | ------------------------------------ |
| Zu breite/dichte Tabellen auf schmalen Viewports | Scrollen, Übersehen wichtiger Spalten             | Viele `console/*`-Tabellen           |
| Signaldetail: zu viele Zeilen ohne Gruppierung   | Orientierungsverlust                              | `signals/[id]/page.tsx`              |
| Technische Statuswörter im Terminal              | Abschreckung für Laien                            | `de.json` → `live.terminal`          |
| Mehrere gleichstarke Aktionen                    | Unklar, was zuerst zu tun ist                     | diverse Panels                       |
| Leerzustände ohne „nächster Schritt“             | Nutzerin bleibt ratlos                            | einzelne Tabellen ohne `help.*`      |
| Diagnose-Modus zeigt Rohfehler                   | Für Support gut — Risiko, wenn fälschlich geteilt | `ConsoleFetchNotice` `showTechnical` |

---

## 8. Tabelle der wichtigsten Sprachprobleme

| Problem                        | Beispiel / Ort                                       | Zielrichtung                                                   |
| ------------------------------ | ---------------------------------------------------- | -------------------------------------------------------------- |
| Rohe Feldnamen in UI           | `market_family`, `playbook_id` in Filtern            | Deutsche Kurzlabels + Tooltip „Fachbegriff: …“ oder nur intern |
| Hartcodierte DE-Labels in Code | `signals/[id]/page.tsx` (`canonical_instrument_id`)  | i18n-Keys + menschliche Namen                                  |
| Abkürzungen ohne Erklärung     | OOD, MAE, MFE, SSE                                   | Ausgeschrieben beim ersten Vorkommen oder Hilfe-Link           |
| Mischsprache EN/DE             | „Take-Trade P“, „Exp. Return“                        | Einheitlich DE oder konsistentes Glossar                       |
| Produkt vs. Designkontrast     | Verbotene Begriffe in `FORBIDDEN_USER_VISIBLE_TERMS` | Manuelle Copy-Reviews für neue Texte                           |
| „Facets“ / „Outbox“            | Hilfe- und Monitor-Texte                             | Optional beibehalten für Ops; für Kunden umschreiben           |

---

## 9. Welche Seiten bereits brauchbar wirken

**Für eine einfache Endkundin (`abgeleitet` aus Texten + Struktur):**

- **Sprachwahl / Welcome** — klare nächste Schritte.
- **Onboarding** — geführt, niedrige Hürde.
- **Konsole Übersicht** (Start) und **einfache Ansicht** mit wenigen Punkten.
- **Account-Hub** und **Assist**-Einstieg — verständliche Rahmenstory.
- **Health** in Kombination mit **Operator Explain** — wenn Umgebung steht, nachvollziehbares „fragen und Antwort bekommen“.
- **Paper** — Metriken und Equity-Chart sind **verständlicher** als Rohsignal-Felder.

**Für Operatorinnen mit Domänenwissen:**

- **Ops**, **Live-Broker**, **Signal-Center** (mit Filter-Hilfe), **Terminal** — **brauchbar**, wenn die Nutzerin **Begriffe wie Timeframe und Pipeline** bereits kennt.

---

## 10. Welche Seiten zu technisch oder zu roh wirken

| Seite / Bereich                                     | Warum                                                                                    |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Signaldetail** (`/console/signals/[id]`)          | Extrem viele interne Feldnamen und Metriken, teils ohne Einsteiger-Kontext               |
| **Signal-Filter (Pro)**                             | Labels wie `specialist_router_id`                                                        |
| **Live-Terminal** (Toolbar/Status)                  | SSE, Ingest, Polling ohne einfache Paraphrase                                            |
| **Admin- und Integrations-Matrix** (falls sichtbar) | erwartungsgemäß dichter — für Laien **nicht** „Kundenoberfläche“                         |
| **Shadow/Live-Vergleich**                           | Fachlogik (Mirror, Divergenz) — sinnvoll für Ops, **hart** für unvorbereitete Leserinnen |

---

## 11. Konkrete Design- und UX-Ziele für 10/10

1. **Signaldetail in Schichten:** Oben **„Kurzfassung für Menschen“** (3–5 Sätze aus vorhandenen Feldern), darunter ausklappbar **„Technische Details“** mit den aktuellen Rohfeldnamen nur für Ops.
2. **Alle sichtbaren Strings über i18n** — keine harten DE-Strings in großen Seiten-Komponenten; EN bleibt vollständig nutzbar.
3. **Filter-Labels:** Überall **deutsche Kurzbezeichnungen**; API-Name nur in Tooltip oder Diagnose.
4. **Glossar oder ?-Links** neben Abkürzungen (MAE/MFE/OOD) **einmal** pro Seite.
5. **Mobile:** Prioritäts-Spalten pro Tabelle definieren; unter `md` **Kartenzeilen** statt 12-Spalten-Tabellen (Designsystem-Vorgabe konsequent).
6. **Terminal:** Umschaltbarer **„einfacher Modus“** für Statuszeilen (verbergen von SSE/Ingest, stattdessen „Echtzeit aktiv / aus“).
7. **Leerzustände:** Überall mindestens **ein Satz + eine Aktion** (wie in `UI_STATE_COPY_KEYS_DE`).
8. **Visuelle QA:** Pflicht-Screenshot-Set (Mobile + Desktop) pro Release für die 10 wichtigsten Flows — Ablage z. B. unter `docs/Cursor/assets/screenshots/` mit Datum.

---

## 12. Übergabe an ChatGPT

**Wenn du über die Oberfläche dieses Repos sprichst:**

1. Unterscheide **einfache Ansicht** vs. **Profi-Konsole** — die Zielgruppe ist nicht dieselbe.
2. Unterscheide **editorialisierte Texte** (`de.json`, Help) von **Rohdaten-Seiten** (Signaldetail).
3. Nimm **Fehlermeldungen** als Stärke — sie sind bewusst nutzerfreundlich klassifiziert.
4. Empfehlungen für Copy: **orientiere dich** an `DESIGN_SYSTEM_MODUL_MATE.md` und `FORBIDDEN_USER_VISIBLE_TERMS` — aber prüfe **immer** die echte `de.json`-Key-Struktur.
5. Für **„ist es mobil gut?“** ohne Screenshots: ehrlich **„nicht verifiziert“** sagen — nur CSS-Breakpoints reichen nicht.

---

## 13. Anhang mit relevanten Dateipfaden

| Thema                                 | Pfad                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Deutsche (und englische) UI-Texte     | `apps/dashboard/src/messages/de.json`, `en.json`                                                  |
| Globale Styles / Layout               | `apps/dashboard/src/app/globals.css`                                                              |
| Konsole-Layout, Nav, Hilfe-Leiste     | `apps/dashboard/src/components/layout/DashboardShell.tsx`, `SidebarNav.tsx`                       |
| Fehler → Text                         | `apps/dashboard/src/lib/user-facing-fetch-error.ts`, `apps/dashboard/src/lib/api-fetch-errors.ts` |
| Fetch-Hinweis-Komponente              | `apps/dashboard/src/components/console/ConsoleFetchNotice.tsx`, `PanelDataIssue`                  |
| Signaldetail (hohe technische Dichte) | `apps/dashboard/src/app/(operator)/console/signals/[id]/page.tsx`                                 |
| Designsystem-Doku                     | `docs/DESIGN_SYSTEM_MODUL_MATE.md`                                                                |
| Design-Tokens (Python-Kanon)          | `shared/python/src/shared_py/design_system_contract.py`                                           |
| Live-Terminal-Copy                    | `de.json` → `live.terminal`, `live.lineage`                                                       |
| Screenshot-Ablage (derzeit leer)      | `docs/Cursor/assets/screenshots/.gitkeep`                                                         |

---

_Ende der Übergabedatei._
