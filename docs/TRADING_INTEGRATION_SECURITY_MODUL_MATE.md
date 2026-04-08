# Trading, APIs, Telegram und Sicherheit (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 7; Kanonischer Code: `shared_py.trading_integration_contract`

---

## Systemlogik fuer Orders

### Trennung der Begriffe

| Stufe              | Bedeutung                                                                               | Wer / was                                     |
| ------------------ | --------------------------------------------------------------------------------------- | --------------------------------------------- |
| **Signal**         | Markt- oder Strategiemeßgroesse (deterministisch oder aus Modellen)                     | Signal-/Feature-Stack, **kein** Kundenauftrag |
| **Empfehlung**     | KI- oder Systemvorschlag in **strukturierter** Form                                     | KI-Schicht + Schema; **keine** Boersenwirkung |
| **Freigabe**       | Explizite Zustimmung (Kunde) und ggf. **kommerzielle Gates** (Vertrag, Admin-Live, Abo) | UI + `product_policy` / `customer_lifecycle`  |
| **Order (Intent)** | Validiertes, idempotentes Auftragsobjekt **vor** Boerse                                 | API-Gateway / Broker-Adapter                  |
| **Ausfuehrung**    | Submit an Exchange **oder** Demo-Simulator                                              | `live-broker` / `paper-broker`                |

**Reihenfolge-Pflicht:** Signal/Empfehlung duerfen die Ausfuehrung **nicht** ueberspringen; Freigabe und Pre-Trade-Checks liegen **vor** Submit.

### Wann simuliert, wann echt?

- **Simuliert (Demo):** wenn `product_policy.resolve_execution_mode` → `demo` (z. B. Probephase oder Vertrag ohne Live-Freigabe) **und** technischer Demo-Pfad aktiv.
- **Echt:** nur wenn **gleichzeitig** Live-Gates erfuellt (`live_trading_allowed`), gueltige Live-API-Verbindung, keine Pause/Sperre, Pre-Trade-Checks gruen.
- **Keine Ausfuehrung:** `none` bei Sperre/Pause oder fehlenden Gates — UI zeigt Grund in **Alltagssprache**.

Siehe `execution_path_for_order` in `trading_integration_contract.py`.

### Ordererstellung, -pruefung, -ausfuehrung, -abbruch

1. **Erstellung:** Client sendet **typisierten** Intent (Symbol, Seite, Menge, Typ) + `client_order_id` (Idempotenz).
2. **Pruefung:** Limits, Rechte, Modus (Demo/Live), Exchange-Status, Rate-Limits.
3. **Ausfuehrung:** eine klar benannte Funktion pro Pfad (`execute_demo` / `execute_live`); **kein** gemischter Codepfad.
4. **Abbruch:** Cancel-Request mit derselben Idempotenz-Disziplin; Ergebnis immer ins Audit.

**Fehlerbehandlung:** unterscheide **wiederholbar** (Netz, 5xx) vs. **final** (ungueltige Order, unzureichendes Margin). Retries nur fuer wiederholbare Fehler mit Cap (siehe `DEFAULT_EXECUTION_RETRY_POLICY`).

---

## Sicherheitskonzept

- **Secrets:** nur in **Secret Store / KMS**; DB traegt `secret_store_key`, niemals Klartext (siehe `commercial_data_model.ApiCredentialRefRecord`).
- **Zugriff:** Broker-Dienst liest Secret **just-in-time**; keine Logs von Schluesseln oder vollstaendigen Signaturen.
- **Rotation:** unterstuetzt; alte Keys **widerrufen** nach Umschalten.
- **Least privilege:** API-Keys mit **minimal** noetigen Boersenrechten.
- **Admin:** volle Einsicht in **Metadaten** und Health, **kein** Klartext-Key in der UI.
- **Kunde:** sieht Verbindungsstatus und **letzte Pruefung**, keine technischen Fehlerrohstrings in Produktion.

**Compliance [RECHTLICH]:** Auftragsdatenverarbeitung, ggf. BaFin-Themen je nach Geschaeftsmodell — extern pruefen.

---

## API-Konzept

- **Eine** primaere Exchange-Integration pro Produktphase ([ANNAHME] Bitget), weitere als Adapter.
- **Healthcheck** getrennt von **Order-Submit** (read-only bzw. signierter Ping).
- **Rate-Limits:** pro Kunde, pro Verbindung, global (siehe `DEFAULT_API_RATE_LIMITS`).
- **Circuit Breaker** bei Exchange-Ausfall; **Notfallstopp** (Admin) vor lokalen Retries stoppen.
- **Idempotenz:** `client_order_id` + serverseitige Dedupe-Tabelle.

---

## Telegram-Konzept

- **Stufe 1 (empfohlen v1):** nur **Benachrichtigungen** (Status, keine Order ohne Web-Freigabe).
- **Stufe 2:** Aktionen nur mit **OTP** und gleichen Gates wie Web-Live.
- **Verknuepfung:** eindeutige `chat_id`, Widerruf jederzeit; bei Sperre Konto **keine** Telegram-Ausloesung.
- **Kein** Speichern von OTP in Logs.

**Compliance [RECHTLICH]:** Einwilligung fuer den Kanal; Nachweis der Verknuepfung.

---

## Protokollierung

**Zwingend** (Append-only, mit `trace_id` wo vorhanden):

- Jede **Freigabeaenderung** (Admin/Kunde).
- Jede **Order**: Intent, Pruefergebnis, Submit, Antwort Exchange, Finalstatus, Modus Demo/Live.
- Jede **Cancel**-Anfrage und Ergebnis.
- **API-Key**-Rotation/Widerruf (ohne Secret).
- **Telegram**-Link/Entlink, kritische Bot-Aktionen.
- **Notfallstopp** global/pro Kunde.

Maschinenlesbare Liste: `MANDATORY_AUDIT_EVENT_TYPES` in `trading_integration_contract.py`.

**Sichtbarkeit:** `VISIBILITY_CUSTOMER` vs. `VISIBILITY_ADMIN_ONLY` — Roh-Fehler nur Admin/Support.

---

## Sichtbarkeit: Kunde vs. Admin

| Information                      | Kunde                         | Admin          |
| -------------------------------- | ----------------------------- | -------------- |
| Orderstatus in Klartext          | ja                            | ja             |
| Exchange-Rohfehlercodes          | nein (verstaendliche Meldung) | ja (technisch) |
| API-Key Klartext                 | nein                          | nein           |
| Key-Metadaten (letzte 4, Rechte) | eingeschraenkt                | ja             |
| Audit vollstaendig               | eigene Aktionen               | alle mit Rolle |
| Notfall-Flags                    | Hinweisbanner                 | Steuerung      |

---

## Offene kritische Risiken

1. **Fehlkonfiguration Demo/Live** — hoechste Prioritaet fuer Tests und Feature-Flags.
2. **Key-Leak** durch Logs, Crash-Dumps oder CI-Artefakte.
3. **Telegram-Account-Uebernahme** — ohne OTP keine Live-Aktionen.
4. **Retry-Stuerme** bei partiellen Ausfaellen — globale Caps und Circuit Breaker.
5. **Regulatorik/Haftung** bei automatisierter Ausfuehrung — **Rechtspruefung**.
6. **Drittland-Uebermittlung** wenn Exchange- oder Cloud-Standorte ausserhalb EU — Vertraege/DPA.

---

## Verweise

- `shared_py.product_policy`, `shared_py.customer_lifecycle`
- `shared_py.ai_layer_contract` (KI vs. Ausfuehrung)
- `shared_py.commercial_data_model` (Order, ExchangeConnection)
- `services/live-broker`, `services/paper-broker`, `services/api-gateway`
