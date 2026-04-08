# Sprache & Nutzerführung — Leitfaden (Dashboard / Frontend)

Gilt für sichtbare Texte in `apps/dashboard/src/messages/en.json` und `de.json` sowie für neue UI. Ziel: **nützlich, klar, freundlich** — ohne leere Marketingfloskeln und ohne interne Entwicklersprache in Nutzerflächen.

---

## 1. Tonfall

- **Du/Sie:** Deutsch konsistent **„du“** (wie im bestehenden Produkt). Englisch **„you“**, direkt und höflich.
- **Stimmung:** ruhig, kompetent, neugierig einladend — nicht belehrend, nicht überschwänglich.
- **Ehrlichkeit:** Lieber zugeben, dass etwas fehlt oder konfiguriert werden muss, als vage „try again“ ohne Kontext.
- **Kein:** „Game-changing“, „seamless“, „best-in-class“, „revolutionary“. Keine leeren Superlative.

---

## 2. Wortregeln

| Statt                                                                  | Besser                                                                                                    |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| „not marketing“ / „no hype“ (in Nutzerüberschriften)                   | Sachlich beschreiben, was die Seite _tut_                                                                 |
| Interne Feldnamen in Fließtext (`execution_authority`, `gateway:read`) | In Hilfe/Admin ok; in Ergebnistexten **Alltagssprache** („cannot place orders“ / „keine Handelsfreigabe“) |
| „AI insights“ als leerer Sammelbegriff                                 | Konkret: „model reports“, „assistant on Health“, „signal context“                                         |
| „Something went wrong“ allein                                          | Kurz **was** + **was du probieren kannst**                                                                |

Fachbegriffe (Signal, Drift, Gateway) nur dort, wo Operatoren sie erwarten; auf der Produktseite eine Ebene einfacher.

---

## 3. Buttons & Aktionen

- **Imperativ oder klare Handlung:** „Save rules“, „Open health“, „Send question“ — nicht „Submit“ ohne Kontext, wenn „Send question“ passt.
- **Ein Haupt-Call-to-Action** pro Bereich wo möglich; sekundäre Aktionen visuell/textlich zurücktreten.
- **Ladezustand:** Verb + Auslassung oder „…“ — „Sending…“, „Loading…“. Kein technisches „Pending request“.
- **Abbrechen:** immer „Cancel“ / „Abbrechen“ oder spezifisch „Cancel request“ / „Anfrage abbrechen“.

---

## 4. Fehlermeldungen

Struktur (wenn Platz):

1. **Was passiert ist** (eine kurze Zeile, ohne Stacktrace).
2. **Was du tun kannst** (1–3 konkrete Schritte oder Verweise).

Beispiel gut: _„We couldn’t load the overview. Check that the API gateway is running, then reload.“_

Beispiel schwach: _„Error 503.“_

Technische Details (ENV-Variablennamen) **in Admin/Dev-Hilfen** ok; in **allgemeinen** Fehlertexten maximal **ein** klarer Hinweis („set server-side gateway auth“) statt zehn Variablen.

---

## 5. Leere Zustände

- **Titel:** neutral-posivit, nicht dramatisch („No open approvals“ statt „Critical failure“).
- **Kurz erklären**, warum leer sein kann (Pipeline, Filter, noch kein Vorgang).
- **Nächste Schritte** als nummerierte oder kurze Liste, wo sinnvoll (bestehendes Muster `step1`/`step2`/`step3` in `help.*`).

---

## 6. Ladezustände

- Kurz; bei langen Operationen Dauer oder Hinweis („can take up to two minutes“) — bereits beim Operator-Assistenten genutzt.
- Kein „Please wait“ ohne Kontext, wenn „Fetching signals…“ möglich ist.

---

## 7. Hilfetexte (`help.*`)

- **brief:** 1 Satz, was der Bereich _für den Nutzer_ bedeutet.
- **detail:** Wie Daten ankommen (Server, nicht Browser), was _nicht_ passiert (kein Ersatz für eigenes Risiko).

---

## 8. Nutzerführung — Ist-Stand & offene Strukturthemen

**Starker Einstieg:**

- Sprache wählen → optional Onboarding → Konsole.
- Einfache Ansicht bündelt Kernorte; Pro öffnet volle Navigation.

**Bekannte strukturelle Punkte** (Text allein reicht nicht):

- **Live-Terminal:** Bei Konfigurationsfehlern erscheinen lange technische Hinweise — für Operatoren nützlich, für Einsteiger überladen; mittelfristig: kurze Meldung + Link „So behebst du das“ / Dokumentation.
- **Learning & Drift:** Sehr technische Untertitel und Tabellen — sinnvoll für Ops, nicht für „erste Orientierung“; ggf. eigene „Einstieg“-Zeile oben.
- **Commerce / Usage:** Hängt an Gateway-Modul; leere Seiten brauchen weiterhin klare „Modul aus oder keine Nutzung“-Erklärung.

---

## 9. Übersetzung EN/DE

- Gleiche _Funktion_: beide Locales müssen dieselbe Handlungsaufforderung tragen.
- Wortwahl: DE nicht 1:1 EN-Kalke; natürliche deutsche Sätze (bereits angestrebt).

---

## 10. Änderungsdisziplin

- Keine rein kosmetischen Umbenennungen ohne UX- oder Klarheitsgewinn.
- Neue Features: zuerst diesen Leitfaden prüfen, dann Keys ergänzen.

**Referenz-Dokumente:** `PRODUCT_STATUS.md`, `release-readiness.md`, `docs/dashboard_operator.md`.

**Umgesetzte Texte (Stand):** In `en.json` / `de.json` u. a. globale Fehler, Health-Untertitel, KI-Frageformular (Titel, Lead, Hinweis, Buttons), Ops-Leads, Trust-Banner und Seitenleisten-Hinweise, Onboarding, Startseite (Hero, KI-Abschnitt, Betrieb), Console-Home (KI-Pfad, Kacheln), Learning-Untertitel, Live-Terminal-Auth-/Proxy-Hinweise (gekürzt, mit klarem Nächste-Schritt).
