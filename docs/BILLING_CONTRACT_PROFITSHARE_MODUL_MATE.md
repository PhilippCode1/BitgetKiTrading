# Zahlungen, Abo, Vertrag und Gewinnbeteiligung (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 8; Kanonischer Code: `shared_py.billing_subscription_contract`

---

## Abo-Modelle

### Feste Richtungen [FEST aus Prompt 8]

- **Tagespreis** ca. **10 EUR netto** (Referenz: `STANDARD_DAILY_NET_CENTS_EUR` im Code).
- **Umsatzsteuer** **19 %** auf die steuerpflichtige Leistung in Deutschland (Standardfall).
- **Intervalle:** Tag, Woche, Monat, Jahr — mit ausgewiesenem Netto/Brutto je Abrechnungszeitraum (siehe `STANDARD_SUBSCRIPTION_PLAN_TEMPLATES`).

### Ableitung der Nettopreise [ANNAHME]

| Intervall | Logik (netto)                                |
| --------- | -------------------------------------------- |
| Tag       | 10 EUR                                       |
| Woche     | 7 × Tagespreis                               |
| Monat     | 30 × Tagespreis (vereinfachtes Monatsmodell) |
| Jahr      | 365 × Tagespreis (Kalenderjahr-Richtwert)    |

Rabatte fuer laengere Laufzeiten sind **nicht** festgelegt — optional spaeter (`BillingReviewTag`).

### Internationale Zahlarten [ANNAHME / zu pruefen]

Ziel: **PayPal, Alipay, Wise, Apple Pay, Google Pay** — soweit **Zahlungsdienst**, **Aufwand** und **Risiko** passen. Technisch erfolgt die Anbindung typischerweise ueber **einen oder mehrere** konforme **PSP-Aggregatoren** (PCI-DSS, starke Kundenauthentifizierung).

**[STEUER/ZAHLUNGSDIENST]** Welche Methode in welchem Land erlaubt ist und wie sie verbucht wird, ist mit **Steuerberater** und **PSP** abzustimmen.

---

## Vertragslogik

### Nachweis und Speicherung

- Annahme der Vereinbarung mit **Zeitstempel**, **Versions-ID** (`ContractVersionRecord`), optional **IP/UA** datensparsam.
- **PDF** oder archivierter Text mit **SHA-256** (`DocumentMetadata`).
- Bei neuer AGB-Version: erneute Zustimmung; Live-Handel bis dahin **sperren** ([ANNAHME], konsistent mit `customer_lifecycle`).

### [FEST] Testphase und Echtgeld

Nach **3 Wochen Probephase** ist fuer den **Echtgeldbetrieb** eine **unterschriebene/angenommene Vereinbarung** erforderlich (zusaetzlich zu Admin-Live-Freigabe und Zahlungsstatus laut `product_policy`).

### Systemstatus ohne Vertrag vs. mit Vertrag

| Zustand                                | Kunde sieht                                              | Technischer Anker                      |
| -------------------------------------- | -------------------------------------------------------- | -------------------------------------- |
| Test aktiv / beendet, **kein** Vertrag | Uebung moeglich; Echtgeld gesperrt mit klarer Checkliste | `LifecyclePhase` vor `CONTRACT_ACTIVE` |
| Vertrag aktiv                          | Abo/Zahlung; Vorbereitung Live; Demo weiter moeglich     | `CONTRACT_ACTIVE` ff.                  |
| Vertrag beendet / superseded           | Zugang und Live nach Produktregel eingeschraenkt         | `ContractStatus`                       |

---

## Zahlungsereignisse

- **Ereignisse:** Autorisierung, Einzug, Fehlschlag, Erstattung, Chargeback — wie `PaymentEventType` im Datenmodell.
- **Rechnung:** nach Leistungszeitraum oder nach Zahlungsausloesung je nach gewaehlter Abrechnungslogik **[STEUER]** klären.
- **Zahlungsausfall:** Eskalationsstufen `DunningStage` im Code (Erinnerung → Sperre → Beendigung).
- **Sperre:** `PAST_DUE` / Pause — **kein** Live-Handel; Demo optional eingeschraenkt (Produktentscheid).
- **Wiederfreigabe:** nach erfolgreicher Zahlung + manuelle Pruefung falls noetig; Audit-Pflicht.

---

## Gewinnbeteiligung

### Fachlich [FEST aus Prompt 8]

**10 %** Gewinnbeteiligung auf die vertraglich definierte **Basis** (z. B. Nettoergebnis nach Boersengebuehren, ggf. High-Water-Mark).

### Technisch

- Abrechnungsperiode `PerformancePeriodRecord`, Regel `ProfitShareRuleRecord`, Buchung `ProfitShareAccrualRecord`.
- Satz **1000 Basispunkte** von 10 000 = **10 %** (`DEFAULT_PROFIT_SHARE_BASIS_POINTS`).

### Vertraglich / buchhalterisch

- **Leistungsart** der Beteiligung (Entgelt, Erfolgsprovision, sonstiges) — **[RECHTLICH/STEUER]** durch Anwalt und Steuerberater.
- **Rechnungsstellung** der Performance-Fee separat oder als Positionszeile (`InvoiceLineType.PERFORMANCE_FEE`).
- **Nachweis:** unveraenderliche `calculation_json`, Export fuer **DATEV** / Steuerberater **[ANNAHME]** Prozess.

---

## Buchhaltungs- und Nachweispflichten

- **Rechnungen** mit fortlaufender Nummer, Ausstellungsdatum, USt-Ausweis (soweit anwendbar).
- **10 Jahre** Aufbewahrung **[ANNAHME]** handels-/steuerrechtlich vs. DSGVO — **Steuerberater**.
- **GoBD**: unveraenderbare Belege nach Ausstellung; Stornos nur **gegenbuchend** / neue Belege.
- **Zahlungsnachweis** ueber PSP-Referenzen (`provider_event_id` unique).

---

## Risikohinweise

1. **USt-Saetze und B2B-EU** (Reverse Charge) veraendern Rechnungsbild.
2. **PSP-Risiken** (Chargebacks, Einbehalte) — Vertraege mit PSP und Reserve.
3. **Alipay/regionale Methoden** — Compliance und Exportkontrollen pruefen.
4. **Gewinnbeteiligung** — Streit ueber Berechnungsbasis; klare Definition und Protokolle.
5. **Regulierung** Finanzdienstleistung — **rechtliche** Einordnung des Gesamtprodukts.

**Marker im Code:** `BillingComplianceReviewTag`.

---

## Verweise

- `shared_py.commercial_data_model` — Rechnung, Steuer-Helfer, Performance-Entitaeten
- `shared_py.customer_lifecycle`, `shared_py.product_policy`
- `shared_py.trading_integration_contract` — Audit bei Zahlungs-Sperren und Live-Gates
