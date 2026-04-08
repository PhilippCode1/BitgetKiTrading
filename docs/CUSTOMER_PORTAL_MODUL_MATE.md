# Kundenportal (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 6; Kanonischer Code: `shared_py.customer_portal_contract`

---

## Seitenaufbau

Zentrale Basis-URL **[ANNAHME]:** `/app` (kurz, international verstaendlich; spaeter optional Sprachpraefix `/de/app`).

| Seite                         | Pfad                 | Zweck in einfacher Sprache                                                                                                  |
| ----------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Start / Uebersicht**        | `/app`               | „Wo stehe ich?“ — naechste Schritte, Modus (Uebung/Echtgeld), kurze Kennzahlen ohne Fachjargon                              |
| **Marktueberblick**           | `/app/markt`         | KI-gestuetzte Erklaerung zu Charts, Signalen und Einordnung — **keine** Roh-Prompts, keine Modellnamen in der Ueberschrift  |
| **Uebungskonto**              | `/app/uebung`        | Alles, was mit **virtuellem Geld** laeuft; klarer Hinweisbanner                                                             |
| **Echtgeldkonto**             | `/app/echtgeld`      | Nur sinnvoll, wenn Vereinbarung und Freigabe erfuellt sind; sonst erklaerender **gesperrter** Zustand mit „Was fehlt noch?“ |
| **Orders**                    | `/app/orders`        | Liste der Auftraege getrennt nach **Uebung** und **Echtgeld** (Tabs oder Filter in Klartext)                                |
| **Verlauf**                   | `/app/verlauf`       | Zeitliche Uebersicht: was wann passiert ist, verstaendlich formuliert                                                       |
| **Abo und Zahlungen**         | `/app/abo`           | Plan, Laufzeit, naechste Zahlung, Rechnungen herunterladen                                                                  |
| **Vereinbarung und Freigabe** | `/app/vereinbarung`  | Status der Vereinbarung, was fuer Echtgeld noch noetig ist, Dokumente                                                       |
| **Telegram**                  | `/app/telegram`      | Verknuepfung, was der Dienst darf, Sicherheit in einfachen Worten                                                           |
| **Einstellungen**             | `/app/einstellungen` | Profil, Sicherheit (z. B. Zwei-Faktor), Benachrichtigungen                                                                  |
| **Hilfe und Support**         | `/app/hilfe`         | Fragen, Kontakt, kurze Erklaerfilme/Platzhalter                                                                             |

**Navigation:** 8–10 Eintraege, gleichwertige Icons + **kurze deutsche** Beschriftungen; keine internen Codes.

---

## Text- und Sprachstil

- **Sie-Form** oder **du-Form** einheitlich waehlen ([OFFEN] — Standard bis Entscheid: **Sie** fuer Vertrauen im Finanzkontext).
- **Aktive Verben:** „Freigabe anfragen“, „Uebung starten“, „Rechnung herunterladen“.
- **Status:** Substantive + Kurzsatz: „Uebungsmodus — Es wird kein echtes Geld bewegt.“
- **Vermeiden:** API, JSON, Modell-IDs, HTTP-Codes, interne Fehlernamen. Stattdessen: „Etwas ist schiefgelaufen. Bitte versuchen Sie es spaeter erneut oder kontaktieren Sie den Support.“
- **Zahlen:** Betraege mit Waehrung, Daten im Kalenderformat des Nutzers (spaeter Locale).
- **Abos:** Intervall immer ausgeschrieben oder klar gekuerzt mit Legende: **Tag**, **Woche**, **Monat**, **Jahr** (siehe `SUBSCRIPTION_INTERVAL_LABELS_DE` im Code).

---

## Zustandswechsel fuer den Kunden

### Probephase (Testkunde)

**Sichtbar:** Start, Marktueberblick, **Uebungskonto**, Orders (Uebung), Verlauf (Uebung), Hilfe, Einstellungen, Telegram (nur Hinweise, keine Echtgeld-Aktionen).  
**Banner oben:** „Sie sind in der Probephase — es handelt sich um **Uebung**, kein Echtgeld.“  
**Echtgeldbereich:** Seite sichtbar, Inhalt **erklaerend gesperrt**: „Nach Vereinbarung und Freigabe nutzbar.“

### Nach Vereinbarung, ohne Echtgeldfreigabe

**Zusaetzlich:** Abo/Zahlungen, Vereinbarung als „aktiv“, ggf. Zahlungsstatus.  
**Echtgeld:** weiterhin gesperrt mit konkreter Checkliste: „Zahlung“, „Anbindung“, „Freigabe durch uns“ — **ohne** Namen interner Systeme.

### Nach Echtgeldfreigabe (Live)

**Echtgeldbereich:** voll nutzbar; **zweiter** klarer Hinweis: echtes Geld, Verlustrisiko.  
**Orders/Verlauf:** Standardansicht **Echtgeld**, Uebung weiter erreichbar.  
**Telegram:** nur wenn Produkt es erlaubt, mit zusaetzlicher Bestaetigung.

### Pause / Sperre

**Globale Meldung** statt leerer Seiten: was eingeschraenkt ist und wie Support hilft.

**Technische Abbildung:** `shared_py.customer_lifecycle` + `derive_customer_capabilities`.

---

## Vertrauens- und Hilfekomponenten

- **Impressum, Datenschutz, Risikohinweis** im Footer (Kundenbereich).
- **Sichtbarer Statusstreifen:** „Konto: … | Modus: Uebung oder Echtgeld | Abo: …“
- **Erklaer-Kaesten** („Kurz erklaert“) mit Platzhalter fuer Video/Bild.
- **Sicherheitssignale:** „Verbindung verschluesselt“, „Zwei-Faktor moeglich“ — ohne Technikdetails.
- **Bei Warnungen:** Farbe + kurzer Text + **was der Nutzer tun kann**.
- **Copy:** siehe `TRUST_COPY_DE` und `MODE_BANNER_*` in `customer_portal_contract.py`.

---

## UX-Fehler, die unbedingt vermieden werden muessen

1. Echten und virtuellen Handel **ohne** visuelle Trennung.
2. Modus nur in kleinem Grautext — muss **prominent** sein.
3. Fehlermeldungen mit Stacktrace oder Feldnamen.
4. Echtgeldaktionen ohne **zweite** Bestaetigung.
5. Leere Seiten ohne Erklaerung (z. B. „Keine Berechtigung“ ohne Kontext).
6. Vermischung von Rechnungs- und Trade-Daten ohne Ueberschriften.
7. Versteckte Kosten — alle Abo-Intervalle und Betraege **vor** Kauf klar.
8. Annahme, der Nutzer kennt Boersenbegriffe — **Glossar** oder Tooltips in Alltagssprache.

**Maschinenlesbar:** `FORBIDDEN_UX_PATTERNS` im Python-Modul.

---

## Offene Punkte

- **Sie/du** und Locale-Strategie (nur DE zuerst vs. mehrsprachig).
- Exakte **Farb- und Typo-Tokens** im Design-System (nicht in diesem Dokument).
- Ob **Echtgeld-Tab** in der Navigation ausgeblendet wird bis freigegeben ([ANNAHME]: sichtbar aber **erklaerend gesperrt**, damit nichts „fehlt“).

---

## Verweise

- `shared_py.customer_lifecycle`, `shared_py.product_policy`
- `shared_py.admin_console_contract` (getrennte Verwaltung)
