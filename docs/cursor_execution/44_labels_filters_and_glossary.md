# 44 — Labels, Filter, Tabellen: Sprachschicht & Glossar

**Bezug:** Handoff `docs/chatgpt_handoff/07_FRONTEND_UX_SPRACHE_UND_DESIGN_AUDIT.md` (Filter mit API-Namen, Terminal SSE/Polling, gemischte Oberfläche).

**Ziel:** Sichtbare Kurzlabels in **verständlichem Deutsch** (bzw. klares Englisch in `en.json`), **interne Feldnamen** nur in **Tooltips** / **Diagnose** / **Technikbereichen**.

**Datum:** 2026-04-05.

---

## 1. Glossar (i18n)

Neuer Namespace **`glossary.console`** in `apps/dashboard/src/messages/de.json` und `en.json` — Begriffe u. a.:

- Echtzeit-Push vs. Abfrage (ehem. SSE / Polling)
- Datenaufnahme (Ingest), Basispunkte, Zeitrahmen
- Marktsegment, Playbook, Ausführungsspur, Router, Exit, OOD, MAE/MFE (Kurzdefinitionen)

**Nutzung:** `title`-Attribute an Tabellenköpfen (`SignalsTable`), Filterzeilen, Ops-Kacheln.

---

## 2. Vorher → Nachher (Auszug)

| Fläche                  | Vorher (sichtbar)                                 | Nachher (sichtbar)                                                | Internes (Tooltip / Fußnote)                           |
| ----------------------- | ------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------ |
| Signale: Filter         | `market_family`, `playbook_id (Schnellwahl)`      | **Marktsegment**, **Playbook (Schnellwahl)**                      | „technisch: market_family“ / `hint*`-Keys              |
| Signale: Facetten-Titel | „Facetten / Datenbasis“, `decision_state (Facet)` | **Datenbasis der Filter**, **Entscheidungszustände (Stichprobe)** | `hintFacetCounts`                                      |
| Signale: Tabelle        | „TF“, „Risk-Gov“, „TT“, „Edge“                    | **Intervall**, **Risiko & Freigabe**, **Handeln**, **Erw. Rand**  | `glossary.console.*` auf `<th>`                        |
| Terminal (DE)           | „(Polling)“, „SSE“ in Hinweisen                   | **(Abfrage)**, **Echtzeit-Push** / **Abfrage**                    | Langtexte ohne Gateway-Akronym im Fließtext wo möglich |
| Ops: Fokus              | `Signal: canonical_instrument_id`                 | **Instrument (interne Kennung)**                                  | `hintOpsCanonicalId`                                   |
| Live-Broker: Abschnitte | „Execution-Decisions“, „Fills“                    | **Ausführungs-Entscheidungen**, **Ausführungen (Fills)**          | —                                                      |
| Learning: Registry      | Zeilen mit ENV-Backticks im Fließtext             | erklärender Satz, **Konfiguration** statt Codezeile               | Detail in Ops-Doku                                     |
| Strategien: Signalpfad  | Satz mit `app.signals_v1`…                        | menschlicher Leitsatz, **Technik in Klammern** am Ende            | —                                                      |

---

## 3. Geänderte / berührte Dateien

| Datei                                                                     | Änderung                                                                                                                                                                                                 |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/dashboard/src/messages/de.json`                                     | `glossary.console`, `pages.signals.filters.*`, `signalsTable.*`, `live.terminal.*`, `pages.ops.*`, `pages.broker.*`, `pages.learning.*`, `pages.strategiesList.*`, `pages.signalsDetail.summaryGlossary` |
| `apps/dashboard/src/messages/en.json`                                     | Parallele Keys und vergleichbare Klärungen                                                                                                                                                               |
| `apps/dashboard/src/app/(operator)/console/signals/page.tsx`              | `title={t("pages.signals.filters.hint…")}` auf Filter-Labels                                                                                                                                             |
| `apps/dashboard/src/app/(operator)/console/ops/page.tsx`                  | Tooltips für Symbol/TF/Marktsegment und Diagnose-Kacheln                                                                                                                                                 |
| `apps/dashboard/src/components/console/ConsoleLiveMarketChartSection.tsx` | Tooltips Zeitrahmen/Symbol (Signale & geteilte Chart-Section)                                                                                                                                            |
| `apps/dashboard/src/components/tables/SignalsTable.tsx`                   | Tabellenköpfe und KPI-Zeilen mit `glossary.console`                                                                                                                                                      |

---

## 4. UI-Nachweise (manuell)

1. **`/console/signals`:** Filterzeilen — deutsche Kurzlabels; mit Maus über Label **Tooltip** mit API-Name.
2. **Signaltabelle:** Spaltenköpfe verständlich; Hover auf **Intervall**, **Risiko & Freigabe**, **Instrument**.
3. **`/console/terminal`:** Statuszeilen ohne harte „SSE“/„Polling“-Kurzform im Primärtext (DE).
4. **`/console/ops`:** Fokus-Panel — keine Rohfeldnamen in den **grauen Überschriften** der Kacheln.
5. **`/console/live-broker`:** Abschnittsüberschriften deutsch konsistent.
6. **`/console/learning`:** Registry-/Drift-Lead ohne Codefence im Fließtext.
7. **`/console/strategies`:** Signalpfad-Hinweis lesbar, Technik hinten.

---

## 5. Automatisierte Prüfungen (2026-04-05)

| Kommando                                       | Ergebnis                                              |
| ---------------------------------------------- | ----------------------------------------------------- |
| `node -e` JSON.parse auf `de.json` + `en.json` | **ok**                                                |
| `pnpm check-types` (Repo-Root)                 | **Exit 0** — `shared-ts` + `dashboard` `tsc --noEmit` |

---

## 6. Offene Punkte

- **[FUTURE]** Weitere Konsolen-Seiten (Admin, Integrationen) können noch englische Tabellenköpfe mischen — gleiches Muster wie hier.
- **[TECHNICAL_DEBT]** Zellwerte (z. B. `trade_action`, `long`) bleiben **API-Werte**; nur Beschriftungen sind lokalisiert.
