# Produkt-Briefing: Trading-KI-Webapp (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 1 (Produktarchitektur)  
**Status:** Feste Vorgaben und Annahmen; rechtliche/steuerliche Punkte extern prüfen.

---

## Legende

| Kennzeichnung          | Bedeutung                                                 |
| ---------------------- | --------------------------------------------------------- |
| **[FEST]**             | Aus stakeholder-Vorgaben, für dieses Briefing verbindlich |
| **[ANNAHME]**          | Standard bis explizite Entscheidung                       |
| **[RECHTLICH/STEUER]** | Extern mit Anwalt, Steuerberater, ggf. Aufsicht klären    |

---

## Teil A: Kurzfassung für die Geschäftsleitung

Modul Mate bietet eine **kommerzielle Trading-KI-Webapp**: für Kunden eine **verständliche, hochwertige Oberfläche**; im Hintergrund **KI-gestützte Unterstützung**, **Trading-APIs**, optional **Telegram**, **lückenlose Protokollierung** und **fortlaufende Datenspeicherung**.

**[FEST]** Es gibt **genau einen Voll-Administrator: Philipp Crljic**. Nur er hat **Vollzugriff** auf die **Gesamt-KI** und **alle Schalter**. Neue Kunden erhalten **3 Wochen Probephase**. In der Probephase soll alles **möglichst realistisch** wirken; **Echtgeldhandel** ist erst nach **Vertrag** und **expliziter Freigabe** erlaubt. **Vor** dieser Freigabe gilt **ausschließlich Demo-Geld**.

**[ANNAHME]** Abo, Zahlungsarten und regulatorische Einordnung werden so gewählt, dass **Buchführung, Steuern und Nachweise** später sauber abbildbar sind.

**[RECHTLICH/STEUER]** Einordnung als Software, Informationsdienst oder Beratung; Vertrags- und Risikoklauseln; Auftragsverarbeitung (z. B. Hosting, OpenAI).

**Erfolgskritisch:** Technische und organisatorische Trennung **Demo vs. Echtgeld**, **Admin-Sicherheit**, und eine **KI-Architektur**, die **später starke OpenAI-Modelle** ohne Umbau der Fachlogik nutzen kann.

---

## Teil B: Vollständige Anforderungsliste (nach Themen)

### Produktziel

- **[FEST]** Kommerzielles Angebot unter **Modul Mate GmbH**; Oberfläche **nutzerfreundlich**, **mittig zentriert**, **ohne sichtbare Code-Sprache** für Endnutzer.
- **[FEST]** Vorbereitung auf **Trading-APIs**, **Telegram-Bot**, **Orderabgabe**, **Protokollierung**, **laufende Datenspeicherung**.
- **[ANNAHME]** Klare Kommunikation: Unterstützung bei Entscheidungen, **kein** Garantieversprechen für Gewinne.

### Nutzergruppen

- **[FEST]** **Super-Admin:** Philipp Crljic.
- **[FEST]** **Kunden** mit **3 Wochen Probephase** zu Beginn.

### Adminrechte

- **[FEST]** Vollzugriff auf **KI-Konfiguration** und **alle Schalter** (u. a. Echtgeld-Freigaben, Integrationen).
- **[ANNAHME]** Starke Authentifizierung (z. B. Passkey) und getrennte Admin-Umgebung.

### Kundenrechte und Pflichten

- **[FEST]** Probephase: realistische Nutzung; **kein Echtgeld** vor Vertrag und Freigabe; **nur Demo-Geld** bis dahin.
- **[ANNAHME]** API-Schlüssel der Börse können vorbereitet werden; **Ausführung** Echtgeld nur nach Freigabe.

### Testphase

- **[FEST]** Dauer **3 Wochen**.
- **[ANNAHME]** Startereignis (z. B. nach E-Mail-Bestätigung und Button „Probephase starten“) im Code über `product_policy` dokumentiert.

### Vertragslogik und Echtgeldfreigabe

- **[FEST]** **Vertrag** und **Freigabe** (durch Admin) sind Voraussetzung für Echtgeldhandel.
- **[ANNAHME]** Freigabe **pro Kunde** mit Notiz und Audit.

### Zahlungslogik

- **[ANNAHME]** Abo über Zahlungsdienst; Anbindung an Rechnungswesen.
- **[RECHTLICH/STEUER]** Umsatzsteuer, Rechnungsfelder, GoBD-relevante Aufbewahrung.

### Trading-, Sicherheits- und KI-Logik

- **[FEST]** Trennung **KI-Schicht**, **Fachlogik**, **Daten**, **Trading-Ausführung**, **Oberfläche**; Erweiterbarkeit für **OpenAI-API**.
- **[FEST]** Nachvollziehbarkeit für wichtige Schritte und Entscheidungen.

### Support und Nachvollziehbarkeit

- **[FEST]** Protokollierung und Datenspeicherung als Anforderung.
- **[ANNAHME]** Support ohne KI-Vollrechte des Admins für andere Personen (später optional).

---

## Teil C: Offene Punkte mit Standardempfehlung

| Thema                   | Standardempfehlung                                                              |
| ----------------------- | ------------------------------------------------------------------------------- |
| Start der 3 Wochen      | Nach **E-Mail-Verifizierung** und explizitem **Start der Probephase**           |
| Freigabe „Echtgeld“     | Admin-Toggle **pro Kunde** mit **Pflichtnotiz**                                 |
| Demo vs. Echt technisch | Zwei Ausführungspfade; Echt nur wenn Vertrag + Freigabe + (optional) Zahlung ok |
| Erste Börse             | Ein Anbieter (z. B. Bitget), weitere später                                     |
| Telegram in Version 1   | Überwiegend **Information**; Echtgeld-Aktionen nur mit zusätzlicher Absicherung |

---

## Teil D: Risiken (früh sichtbar)

1. **Regulatorik** bei Handelsunterstützung und Ausführung.
2. **Erwartungsmanagement** der Kunden (Verluste, KI-Grenzen).
3. **Fehlkonfiguration** Demo/Echtgeld (hohes Schadenpotenzial).
4. **API-Schlüssel** und Account-Takeover (Telegram, Web).
5. **Datenübermittlung** an KI- und Cloud-Anbieter (DSGVO).
6. **Einzel-Admin:** Notfall- und Zugangsplan ohne dauerhaften zweiten Voll-Admin.

---

## Implementierung im Repository

Maschinenlesbare **feste Vorgaben** und **Gate-Hilfen** liegen in:

`shared/python/src/shared_py/product_policy.py`

Änderungen an **[FEST]**-Werten sollten bewusst versioniert und mit diesem Dokument abgeglichen werden.
