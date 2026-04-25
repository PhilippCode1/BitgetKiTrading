# Cursor Work Protocol

Dieses Protokoll ist fuer Cursor-Arbeit in `bitget-btc-ai` verbindlich. Es
konkretisiert `AGENTS.md` fuer die neue private deutsche Main-Console-
Ausrichtung.

## 1. Vor jedem Prompt

Cursor muss bei jedem Prompt relevante Dateien lesen, bevor Aenderungen gemacht
werden. Mindestens zu pruefen sind:

- direkt betroffene Code-, Test- und Doku-Dateien
- `AGENTS.md`
- relevante Dateien unter `docs/production_10_10/`
- bei UI-Arbeit die betroffenen deutschen Texte, Routen und Main-Console-
  Komponenten
- bei Trading-/Risk-/Live-Arbeit die Gate-, ENV-, Broker-, Reconcile- und
  Safety-Dokumentation

## 2. Produkt-Scope pruefen

Cursor muss jede Aufgabe gegen den privaten Owner-Scope pruefen:

- einziger Nutzer: Philipp Crljic
- keine Kunden
- keine Mandanten
- kein Billing
- kein Verkauf
- keine Payment- oder Subscription-Flows
- deutsche Main Console als zentrale Oberflaeche
- Bitget-Multi-Asset-Faehigkeit nur mit strengen Fail-closed-Gates

Wenn ein Prompt Customer-, Billing-, Sales- oder Multi-Tenant-Richtung staerkt,
muss Cursor das als Scope-Konflikt benennen und eine private Main-Console-
Alternative vorschlagen oder um explizite Klaerung bitten.

## 3. Umsetzungspflicht

Cursor muss konkrete Aenderungen programmieren, wenn der Prompt Umsetzung
verlangt. Eine reine Erklaerung ersetzt keine Umsetzung. Bei nicht-trivialer
Arbeit muss Cursor kurz planen und dann umsetzen.
Ein Prompt gilt erst als abgeschlossen, wenn Umsetzung, Tests/Checks und
Dokumentation konsistent nachgewiesen sind oder ein externer Blocker exakt
benannt ist.

Minimaler Arbeitsablauf:

1. Repository und relevante Dateien lesen.
2. Problem, Produkt-Scope und Live-Geld-Risiko verstehen.
3. Plan fuer Aenderung, Tests und Doku bilden.
4. Minimal-invasive Aenderungen machen.
5. Passende Tests oder Checks ergaenzen, wenn Verhalten geaendert wird.
6. Passende Checks ausfuehren.
7. Fehler analysieren, korrigieren und erneut pruefen.
8. Abschluss mit Evidence, Restrisiko und naechstem Pflichtschritt liefern.

## 4. Test- und Checkpflicht

Cursor muss passende Tests ergaenzen, wenn Verhalten geaendert wird. Bei reinen
Doku- oder Scope-Aenderungen muessen mindestens die vorhandenen Release-Gates
geprueft werden, soweit lokal ausfuehrbar:

```bash
python tools/release_sanity_checks.py
python tools/check_release_approval_gates.py
```

Wenn ein Check fehlt oder wegen lokaler Umgebung scheitert, muss Cursor exakt
dokumentieren:

- Befehl
- Exit-Code, soweit vorhanden
- relevante Fehlermeldung
- Einordnung als Repo-Blocker, lokaler Umgebungsblocker oder externer Blocker
- konkreter Nachholpfad

## 5. Selbstkorrektur

Wenn ein Check wegen Cursor-Aenderungen fehlschlaegt, muss Cursor den Fehler
analysieren, korrigieren und den Check erneut ausfuehren. Cursor darf erst
fertig melden, wenn der Prompt wirklich umgesetzt ist oder ein externer Blocker
exakt benannt ist.

## 6. Harte Verbote

- Keine echten Secrets erzeugen, anzeigen, loggen oder speichern.
- Keine echten Bitget-Orders ausloesen.
- Keine Live-Defaults aktivieren.
- Keine Billing-, Customer-, Sales-, Payment- oder Subscription-Features als
  Ziel ausbauen.
- Keine englischen UI-Texte fuer die finale Anwendung einfuehren.
- Keine `10/10 erreicht`-Behauptung ohne Evidence.
- Keine fremden Worktree-Aenderungen zuruecksetzen.

## 7. Abschluss-Evidence

Jeder Abschluss muss berichten:

- erstellte oder geaenderte Dateien
- wie die private Main-Console-Entscheidung eingehalten wurde
- welche Live-/No-Go-Regeln betroffen sind
- welche Checks gelaufen sind
- welche Checks fehlschlugen und warum
- ob echtes Live-Geld weiterhin blockiert ist
- welcher naechste Prompt zwingend folgen sollte
