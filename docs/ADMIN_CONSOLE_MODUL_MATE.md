# Admin-Konsole (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 5; Kanonischer Code: `shared_py.admin_console_contract`

---

## Zielgruppe

**Einziger Voll-Administrator:** Philipp Crljic ([FEST]). Die Konsole ist die **Zentrale** fuer
Kunden, Freigaben, KI-Steuerung, Zahlungen, Anbindungen und Notfaelle.

---

## Informationsarchitektur

1. **Lagebild** — Dringlichkeiten und Kennzahlen
2. **Kunden** — Lebenszyklus, Detailtabs, Aktionen
3. **Vereinbarungen und Zahlungen** — Rechnungen, Abos
4. **Anbindungen** — Boerse, Telegram (Uebersichten)
5. **Kuenstliche Intelligenz** — Textbausteine, Grenzen, Modellwahl
6. **Sicherheit und Notfall** — globale Schalter
7. **Berichte** — Kennzahlen, Exporte
8. **Hilfe** — Kurzanleitungen, Platzhalter fuer Medien

---

## UX-Regeln (Kurz)

- **Sprache:** Klartext auf Buttons und Menues — **keine** technischen Feldnamen oder API-Begriffe.
- **Layout:** ruhig, professionell, **mittig begrenzte** Arbeitsbreite.
- **Kritische Aktionen:** Bestaetigungsdialoge nach `ConfirmationTier` im Code.
- **Medien:** feste **Erklaer**-Platzhalter (Bild/Video) auf groesseren Seiten.

---

## Seitenbaum (URL-Basis)

Basis: `ADMIN_CONSOLE_BASE_PATH` = `/verwaltung` ([ANNAHME], aenderbar nur konsistent mit Frontend).

Siehe `ADMIN_ROUTES` und `AdminNavItem` in `admin_console_contract.py`.

---

## Zentrale Kennzahlen (Start)

Definiert als `DashboardKpiId` — Anzeigenamen auf Deutsch in `KPI_LABELS_DE`.

---

## Verweise

- `shared_py.customer_lifecycle` — Phasen und Admin-Transitions
- `shared_py.product_policy` — Super-Admin-Name, Demo/Live
- `shared_py.commercial_data_model` — Rechnungen, Freigaben, Audit
