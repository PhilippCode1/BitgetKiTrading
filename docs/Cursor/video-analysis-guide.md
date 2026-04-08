# Video vollstaendig analysieren — Arbeitsnotizen

Ziel: **jeden relevanten Inhalt** erfassen, **Zusammenhaenge** verstehen und **nichts Wichtiges** uebersehen — fuer Reviews, Bugs, Onboarding oder Cursor-Chats.

---

## 0. Vor dem ersten Abspielen

- **Metadaten notieren:** Dateiname, Laenge, Aufnahme-Datum (falls bekannt), Wer hat aufgenommen / welches Ziel?
- **Fragestellung fixieren:** Was soll nach diesem Video klar sein? (z. B. „Bug reproduzieren“, „Flow der Einstellungen“, „Entscheidung im Meeting“.)
- **Technik:** Ton an? Untertitel vorhanden? Mehrere Kameraperspektiven / nur Screen?

---

## 1. Erster Durchlauf (Orientierung, nicht bewerten)

- **Grobe Kapitel** mit Timestamp markieren (z. B. `0:00 Intro`, `2:15 Login`, `5:40 Fehler`).
- **Modus pro Abschnitt:** Screen-only, Person sichtbar, Folien, Mischform.
- **Erster Eindruck:** Was ist die **Kernaussage** oder der **Hauptpfad**?

---

## 2. Zweiter Durchlauf (systematisch, segmentweise)

Pro **Kapitel** oder **30–90-Sekunden-Block** festhalten:

| Aspekt                  | Was erfassen                                                                     |
| ----------------------- | -------------------------------------------------------------------------------- |
| **Bild**                | Welche UI / welche Seite / welcher Dialog? Scroll, Klick, Hover, Ladezustand?    |
| **Text auf dem Screen** | Woertlich oder Screenshot; Fachbegriffe, Fehlermeldungen, URLs, Versionsnummern. |
| **Audio / Sprache**     | Sinngemaess + ggf. woertliche Zitate bei Entscheidungen oder Zahlen.             |
| **Aktionen**            | Reihenfolge: „erst X, dann Y“; Tastatur vs. Maus.                                |
| **Erwartung vs. Ist**   | Was sollte passieren? Was passiert? (wichtig fuer Bugs)                          |

---

## 3. Dritter Durchlauf (Lücken & Praezision)

- **Unklare Stellen** nochmal ansehen (zurueckspulen, langsamer).
- **Alles, was im Chat/Repo gebraucht wird, belegen:**  
  kritische Frames als **Screenshots** nach `docs/Cursor/assets/screenshots/` mit sprechendem Namen.
- **Zahlen, Namen, Versionen** doppelt pruefen (oft verlesen oder nur kurz sichtbar).

---

## 4. Synthese (Verstaendnis schliessen)

Am Ende eine **kurze strukturierte Zusammenfassung** schreiben:

1. **Zweck des Videos** (ein Satz).
2. **Ablauf / Storyline** (nummerierte Liste mit Timestamps).
3. **Fakten & Entscheidungen** (bullet points).
4. **Offene Fragen** (was unklar blieb oder gefehlt hat).
5. **Naechste Schritte** (was im Code, in der Doku oder im Ticket passieren soll).

Diese Synthese in `video-review-notes.md` unter dem Video-Eintrag ablegen oder als eigenes Kapitel unten anhaengen.

---

## 5. Fuer Cursor / KI im Chat

- **Video-Datei** kann angehaengt werden, wenn der Client das unterstuetzt; sonst: **Screenshots + Transkript** (manuell oder Tool) + **Timestamps** aus dieser Anleitung.
- **Immer mitgeben:** Ziel der Analyse, die **Synthese** (Abschnitt 4) und die **timestampierten Notizen** aus `video-review-notes.md`.
- So ist das Modell nicht auf „einmaliges Hinsehen“ angewiesen, sondern auf **strukturierte Evidenz**.

---

## Kurz-Checkliste (abhacken)

- [ ] Laenge & Kapitel-Timestamps
- [ ] UI-Zustaende & sichtbare Texte erfasst
- [ ] Sprache / Entscheidungen sinngemaess dokumentiert
- [ ] Kritische Momente als Screenshots im Asset-Ordner
- [ ] Synthese + offene Fragen geschrieben
- [ ] Verknuepfung zu Prompt / Ticket / PR klar

Siehe auch: `chat-workflow.md`, `video-review-notes.md`.
