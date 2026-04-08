# Sprach- und Inhaltsleitfaden (verbindlich)

Gültig für alle sichtbaren Texte der Website (Dashboard, öffentliche Seiten, Hilfen, BFF-Fehlermeldungen, die Nutzer sehen). Technische Logs und reine Code-Kommentare sind ausgenommen, sofern nicht nutzerorientiert.

---

## 1. Grundhaltung

- **Menschlich:** Sätze vollständig, natürlicher Wortlaut — wie eine kompetente Kollegin, nicht wie ein Statuscode.
- **Freundlich und ruhig:** Kein Druck, keine Übertreibung, keine Angstmache.
- **Kompetent:** Fakten nennen, nächsten sinnvollen Schritt andeuten, wo möglich.
- **Vertrauenswürdig:** Keine Gewinngarantien, keine verschwiegenen Risiken; bei Unsicherheit ehrlich bleiben.
- **Knapp + nutzbringend:** Jeder Absatz soll dem Leser eine klare Information oder Handlung liefern — keine Füllwörter.

---

## 2. Anrede und Grammatik

- **Deutsch:** Durchgängig **„du“** (kleingeschrieben), direkte Ansprache wo sinnvoll („Prüfe …“, „Du siehst …“).
- **Englisch:** **„you“**, gleicher Ton wie oben.
- Rechtschreibung: Projektkonvention **ohne Eszett** in UI-Strings (`ae`, `oe`, `ue`, `ss`), außer Zitate aus externen APIs.
- Keine Doppelungen („sehr sehr“), keine leeren Superlative.

---

## 3. Fachbegriffe

- Fachbegriffe (z. B. **Drift**, **Shadow**, **Live-Gate**, **bps**) nur verwenden, wenn sie in der Konsole schon etabliert sind.
- Beim ersten Vorkommen oder in operatorlastigen Texten: **kurze Erläuterung in Klammern oder im nächsten Satz** (ein Satz genügt).
- Englische UI-Reste (z. B. `warn`, `hard_block`) in **Code-Format** (`backticks`) oder klar als technischer Wert kennzeichnen.

---

## 4. Startseite und Marketing-adjazente Bereiche

- Keine leeren Versprechen („alles automatisch“, „sicherer Gewinn“).
- Nutzen konkret: was der Nutzer **sieht**, **entscheidet**, **prüfen kann**.
- Disclaimer klar und fair (keine Anlageberatung, kein Ersatz für eigenes Risikomanagement).

---

## 5. Navigation und Buttons

- Navigation: **Substantive oder kurze Nominalgruppen** („Signal-Center“, „Mein Konto“), keine Sätze.
- Buttons: **Verb im Imperativ** oder klare Handlung („Speichern“, „Checkout starten“, „Weiter“).
- Keine rein technischen Labels als einziger Button-Text für Laien (`POST /v1/...` nur als Zusatz, nicht als Primäraktion).

---

## 6. Überschriften

- **H2/H3:** Inhalt beschreiben, nicht „Info“ oder „Details“.
- Untertitel (`Header subtitle`): **ein Satz**, Kontext + Einschränkung wo nötig.

---

## 7. Formulare und Eingaben

- **Label** klar; **Hinweis** (`hint`): Format, Grenzen, Speicherort (serverseitig …).
- Platzhalter in Feldern: Beispielwert oder Kurzbeschreibung, kein „test“ oder „foo“.

---

## 8. Ladezustände

- Form: **Präsens + „…“** („Wird gesendet …“, „Lade Zahlungsoptionen …“).
- Kurz erklären, _was_ lädt, wenn es länger dauern kann.
- Kein „Bitte warten“ ohne Kontext.

---

## 9. Fehlermeldungen

- **Struktur:** Was ist passiert (menschlich) + optional **was der Nutzer tun kann** (ein Schritt).
- Kein roher Stacktrace für Endnutzer; technische Details in ausklappbaren Bereichen oder für Admins.
- HTTP-Status allein reicht nicht — kurze Einordnung („Wir erreichen den Server gerade nicht“ statt nur „502“).

---

## 10. Leere Zustände

- **Titel:** neutral-positiv („Noch keine Signale für diese Filter“).
- **Text:** warum leer sein kann + **ein konkreter nächster Schritt** (Filter lockern, Stack prüfen, später erneut öffnen).

---

## 11. API- und Verbindungsfehler (UI)

- Einheitliches Präfix aus Übersetzungskeys (`errors.apiPrefix` o. ä.): z. B. „Wir konnten die Daten gerade nicht laden.“
- Danach technische Detailnachricht aus dem Server, falls vorhanden.

---

## 12. Erfolgsnachrichten

- Kurz, bestätigend, ohne Übertreibung („Gespeichert.“ / „Regeln sind übernommen.“).
- Bei Hintergrundjobs: was passiert ist + wo der Nutzer den Effekt sieht.

---

## 13. KI- und Modelltexte (in der Oberfläche)

- Kein „Die KI sagt kaufen“ — Formulierungen wie **Einschätzung**, **Vorschlag**, **Hinweis**.
- Unsicherheit und Grenzen der Automatisierung klar benennen.
- Wenn Inhalte aus dem LLM kommen: Nutzer wissen lassen, dass es **unterstützende Texte** sind, keine Weisung.

---

## 14. Einheitliche Begriffe (DE)

| Begriff                     | Vermeiden                                     |
| --------------------------- | --------------------------------------------- |
| Konsole / Operator-Konsole  | „Backend-UI“, „Panel“ allein                  |
| Freigabe                    | „Approval“ als einziger Begriff auf DE-Seiten |
| Paper / Übungsmodus         | „Fake-Geld“ (außer erklärend)                 |
| Live (Echtgeld-Pfad)        | „Real“ ohne Kontext                           |
| Signal (Systemeinschätzung) | „Kaufempfehlung“                              |

---

## 15. Umsetzung im Code

- **Bevorzugt:** alle nutzersichtbaren Strings in `apps/dashboard/src/messages/de.json` und `en.json` (Keys unter `pages.*`, `console.*`, `errors.*`, `help.*`, …).
- **Client-Komponenten:** `useI18n()`; **Server-Komponenten:** `getServerTranslator()`.
- Neue Texte: immer **beide Sprachen** pflegen.

---

## 16. Review-Checkliste (vor Merge)

- [ ] Ton: freundlich, klar, ohne Floskeln
- [ ] „du“ / „you“ konsistent
- [ ] Fachbegriffe erklärt oder eingeführt
- [ ] Buttons und Fehler verständlich ohne Entwicklerjargon
- [ ] Leer- und Ladestates mit nächstem Schritt
- [ ] DE + EN angeglichen

---

_Dokumentversion: 2026-04-02 — bei größeren Produktänderungen Abschnitt 14 und Beispiele aktualisieren._
