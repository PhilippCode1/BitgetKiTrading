# Designsystem, Oberflaechenstil und Inhaltsregeln (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 9; Kanonischer Code: `shared_py.design_system_contract`

---

## Designsystem

### Grundprinzipien

- **Ruhig, serioes, modern** — keine grellen Neon-Farben, kein „Crypto-Spielzeug“.
- **Vertrauen** — viel Weissraum, klare Hierarchie, konsistente Raster.
- **Mittig zentriert:** Hauptinhalt in einem **max. 1120 px** breiten Container (`CONTENT_MAX_WIDTH_PX`), zentriert auf grossen Viewports.
- **Eine** Primaerfarbe, **eine** neutrale Skala, **semantische** Akzente fuer Status.

### Farben (Referenz)

Siehe `COLOR_SEMANTIC_HEX` im Code. Kurz:

| Rolle                             | Verwendung                   |
| --------------------------------- | ---------------------------- |
| Canvas                            | Seitenhintergrund, sehr hell |
| Surface                           | Karten, Modals               |
| Border                            | dezente Linien               |
| Text primary / muted              | Fliesstext, Sekundaeres      |
| Primary                           | Primaeraktionen, Links       |
| Success / Warning / Danger / Info | Status, nur sparsam          |

### Abstaende und Raster

- Basis **4 px**; uebliche Stufen **8, 12, 16, 24, 32, 48, 64** (`SPACING_PX`).
- Karteninnenabstand: **24 px** horizontal, **20–24 px** vertikal.
- Sektionsabstand: **32–48 px**.

### Ecken und Schatten

- Karten: **12 px** Radius (`RADIUS_CARD_PX`).
- Buttons, Inputs: **8 px**.
- Schatten: **eine** deutsche Stufe fuer erhobene Karten (`ELEVATION_CARD`), keine starken Drops.

### Typografie

- Systemschriftstack **ohne** exotische Webfonts-Pflicht [ANNAHME]: `TYPOGRAPHY_FONT_STACK_CSS`.
- H1–H3 klar gestaffelt; **max. 2 Schriftgroessen** fuer Fliesstext (Body / Klein).

---

## Komponentenregeln

### Karten

- Eine klare **Ueberschrift**, optional **Untertitel** in muted.
- Aktionen **rechts unten** oder in einer **Toolbar** oben — nicht verstreut.

### Tabellen

- **Zebra optional**, immer **hover**-Zeile.
- Zahlen **rechtsbuendig**, Waehrungen mit **Einheit**.
- Auf Mobile: **Kartenstapel** statt horizontal scrollender Mini-Tabelle (wenn moeglich).

### Buttons

- **Primaer:** eine Hauptaktion pro Bildschirmbereich.
- **Sekundaer:** Outline oder Ghost.
- **Destruktiv:** nur mit Bestaetigungsdialog; Farbe `danger`.

### Formularfelder

- **Label** immer sichtbar (nicht nur Placeholder).
- Fehler **unter** dem Feld in Klartext.
- Pflichtfelder mit **\* oder Text** „erforderlich“.

### Warnungen und Statuschips

- **Info** (blau-grau), **Erfolg** (gedecktes Gruen), **Hinweis** (Bernstein), **Kritisch** (Rot) — aus `SEMANTIC_STATUS_TONE`.
- Chips: **kurzes** Substantiv + optional Icon; **kein** technischer Code im Chip-Text.

### Charts, KI-Hinweise, Konten, Zahlungen

- **Charts:** Achsenbeschriftung in **Alltagssprache**; Legende **vollstaendige Woerter**; Tooltips **ohne** interne Serien-IDs.
- **KI:** „Einordnung“ / „Hinweis“ statt „Prompt“ oder Modellname in der Ueberschrift.
- **Kontostatus:** Modus **Uebung / Echtgeld** prominent (Banner oder Chip neben Kontonamen).
- **Zahlung:** Status in Woertern („Bezahlt“, „Ausstehend“, „Erneut versuchen“), nicht `paid`/`pending`.

### Platzhalter Medien

- Fester **16:9**-Rahmen, Hintergrund `surface-muted`, **Titel** „Kurz erklaert“ (`MEDIA_PLACEHOLDER_*` im Code).

---

## Admin vs. Kunde (gleiche Marke, andere Dichte)

| Aspekt       | Kunde                            | Admin                                         |
| ------------ | -------------------------------- | --------------------------------------------- |
| Breite       | eng zentriert, grosszuegig       | gleiche Tokens, **Sidebar** links moeglich    |
| Dichte       | grosszuegiger                    | etwas **kompaktere** Tabellen erlaubt         |
| Sprache      | maximal einfach                  | sachlich, weiterhin **ohne** Dev-Jargon in UI |
| Primaerfarbe | identisch                        | identisch                                     |
| Navigation   | unten (Mobile) / oben oder links | Sidebar **Verwaltung**                        |

---

## Sprachregeln

- **Buttons:** Verb + Ziel („Rechnung herunterladen“, nicht „Download“).
- **Titel:** beschreibend, **keine** internen Codes.
- **Hinweise:** kurz, mit **naechstem Schritt**.
- **Fehler:** „Es ist ein Problem aufgetreten. Bitte …“ + optional technische ID **nur** in „Details fuer Support“.
- **Erfolg:** bestaetigen, was erreicht wurde („Gespeichert“, „Zahlung eingegangen“).

Vollstaendige No-Go-Begriffe: `FORBIDDEN_USER_VISIBLE_TERMS` im Code.

---

## Responsiv-Regeln

- **Mobile-first** [ANNAHME]; Breakpoints: `BREAKPOINT_MIN_WIDTH_PX`.
- **Touch-Ziele** min. **44 px** Hoehe.
- **Schrift** auf Mobile nicht kleiner als **16 px** fuer Eingabefelder (Zoom-Vermeidung iOS).

---

## Leere-, Lade-, Fehler-, Erfolgszustaende

- **Leer:** Illustration optional; **ein Satz**, was fehlt; **eine** Handlung.
- **Laden:** Skeleton oder dezenter Spinner + Kurztext.
- **Fehler:** Icon + Klartext + Retry / Support.
- **Erfolg:** kurz, auto-dismiss oder „Schliessen“.

Schluessel fuer konsistente Texte: `UI_STATE_COPY_KEYS_DE` im Code.

---

## No-Go-Liste fuer schlechte UX

1. Technische Begriffe aus `FORBIDDEN_USER_VISIBLE_TERMS`.
2. Modus (Demo/Echtgeld) verstecken.
3. Mehrere primaere Buttons ohne Hierarchie.
4. Fehler ohne Handlungsoption.
5. Tabellen ohne Mobile-Strategie.
6. Uebermaessige Animationen.

Ergänzend: `FORBIDDEN_UX_PATTERNS` in `customer_portal_contract`.

---

## Offene Punkte

- Finale **Markenfarbe** (Primaer) mit Markenverantwortlichen abstimmen.
- **Echte** Illustrationen / Fotos — Platzhalter bis Lieferung.
- **Dark Mode** — optional Phase 2 (nicht in v1 Pflicht).

---

## Verweise

- `shared_py.customer_portal_contract`, `shared_py.admin_console_contract`
- `docs/CUSTOMER_PORTAL_MODUL_MATE.md`, `docs/ADMIN_CONSOLE_MODUL_MATE.md`
