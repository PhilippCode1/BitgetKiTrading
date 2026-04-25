# Teil 9/10: Endnutzer-Oberflaeche und Produkt (50 % Gewicht)

---

## 1. Web-Frontend fuer Kunde/Admin

**Pruefmethode:** Suche nach typischen Frontend-Artefakten (`package.json` im Root-Webapp, `apps/web`, Next.js).

**Ergebnis:** **Kein** separater `web/`-Wurzel-Workspace: Kunden- und Admin-Oberflaeche liegen im **Dashboard** (`apps/dashboard`) als Route-Gruppen.

**Konsequenz:** Die **Haelfte** der Zielbewertung („Oberflaeche“) ist fuer ein **serioeses** Modul-Mate-Produkt **nicht** erfuellt — unabhaengig von der Backend-Qualitaet.

---

## 2. Spezifikationen und Texte (ohne UI)

Es existieren **maschinenlesbare** Kontrakte:

- `shared_py/customer_portal_contract.py` — Routen `/app`, deutsche Labels
- `shared_py/admin_console_contract.py` — `/verwaltung`, KPIs, Bestaetigungsstufen
- `shared_py/design_system_contract.py` — Farben, No-Go-Begriffe

**Beleg (Nav-Eintraege Kunde — nur Code, keine renderbare UI):**

```74:98:shared/python/src/shared_py/customer_portal_contract.py
CUSTOMER_PRIMARY_NAV: tuple[CustomerNavItem, ...] = (
    CustomerNavItem(
        CustomerPortalPageId.HOME,
        "",
        "Uebersicht",
        "Ihr aktueller Stand, naechste Schritte und Modus.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.MARKET,
        "markt",
        "Markt und Einordnung",
        "Charts, Signale und verstaendliche Bewertung — ohne technische Details.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.PRACTICE,
        "uebung",
        "Uebungskonto",
        "Alles mit virtuellem Geld. Ideal zum Kennenlernen.",
    ),
    CustomerNavItem(
        CustomerPortalPageId.LIVE,
        "echtgeld",
        "Echtgeldkonto",
        "Echte Boersenauftraege — nur wenn freigegeben.",
    ),
```

(weitere Nav-Eintraege in derselben Datei bis ca. Zeile 145)

**Bewertung:** **Hoch** fuer **Planung** und **Vorbereitung** — **niedrig** fuer **lieferbare UX**.

---

## 3. DB: Portal-Tabellen ohne sichtbare UI

`598_customer_portal_domain.sql` legt Tabellen an — **Backend-Bereitschaft**, keine **Oberflaeche**.

---

## 4. Teilbewertung Teil 9 (nur Oberflaeche/Produkt)

| Dimension                         | Stufe (1–10) | Kurzbegruendung                         |
| --------------------------------- | ------------ | --------------------------------------- |
| Shippable Web-App Kunde           | **1–2**      | Nicht im Repo nachweisbar               |
| Shippable Web-App Admin (Philipp) | **1–2**      | Nicht im Repo nachweisbar               |
| UX-Spezifikation als Code         | **7**        | Portal/Admin/Design-Kontrakte vorhanden |
| Vertrauenswirkung Endkunde        | **2**        | Ohne UI keine echte Bewertung moeglich  |

---

**Naechste Datei:** `10_gesamtfazit_stufenmatrix.md`
