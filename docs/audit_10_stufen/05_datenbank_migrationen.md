# Teil 5/10: Datenbank und Migrationen

---

## 1. Umfang

**74** SQL-Dateien unter `infra/migrations/postgres/` — inkl. Live-Broker, Paper-Broker, Learning, Alerts, **kommerzielle** und **Portal**-Tabellen.

---

## 2. Kundenportal / Zahlungen (Schema vorhanden)

```4:29:infra/migrations/postgres/598_customer_portal_domain.sql
CREATE TABLE IF NOT EXISTS app.customer_profile (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    display_name text,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    ...
);

CREATE TABLE IF NOT EXISTS app.customer_payment_event (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    amount_list_usd numeric(18, 8) NOT NULL,
    currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL,
    provider text NOT NULL DEFAULT 'manual',
    provider_reference_masked text,
    notes_public text,
    created_ts timestamptz NOT NULL DEFAULT now()
);
```

**Bewertung:** **Persistenz** fuer Portal-Zahlungsereignisse ist **vorbereitet**; `provider` default `manual` deutet auf **noch nicht** produktiven PSP-Betrieb.

---

## 3. Abgleich mit `shared_py.commercial_data_model`

Die Pydantic-Modelle (z. B. `InvoiceRecord`, `PaymentEventRecord`) aus Prompt 4 sind **logisch** — eine **1:1-ORM-Abbildung** auf alle Migrationen wurde im Audit **nicht** Zeile fuer Zeile verifiziert.

**Luecke fuer andere KI:** Mapping-Tabelle „Python-Modell → SQL-Tabelle → Service“ fehlt als zentrales Dokument.

---

## 4. Teilbewertung Teil 5

| Dimension                                | Stufe (1–10) | Kurzbegruendung                                                  |
| ---------------------------------------- | ------------ | ---------------------------------------------------------------- |
| Migrationsdisziplin                      | **8**        | Viele versionierte SQLs, Indizes, Kommentare                     |
| Kommerz / Portal                         | **5**        | Tabellen da, aber nicht klar voll integriert                     |
| Konsistenz zu Modul-Mate-Datenmodell-Doc | **4**        | Python-Kontrakte und DB teils parallel ohne Nachweis der Deckung |

---

**Naechste Datei:** `06_ki_llm_schicht.md`
