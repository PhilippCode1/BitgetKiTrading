# Fachliches Datenmodell (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 4; Kanonischer Code: `shared_py.commercial_data_model`

---

## Ueberblick

Logisches Rueckgrat fuer **Kundenkonto**, **Probephase**, **Vertraege**, **Abo**, **Rechnungen**,
**Zahlungen**, **Demo/Echtgeld**, **Boersen-API**, **Telegram**, **Orders**, **Gewinn/Beteiligung**,
**Freigaben**, **Sperren**, **Audit**, **Supportnotizen** und **Dokumente**.

Persistenz (Postgres etc.) implementieren die Services; dieses Paket liefert **stabile Typen**
und **Berechnungshilfen** (z. B. USt).

---

## Kernobjekte (Kurz)

| Bereich          | Modell / Enum im Code                                                          |
| ---------------- | ------------------------------------------------------------------------------ |
| Organisation     | `OrganizationRecord`                                                           |
| Kunde            | `CustomerAccountRecord`                                                        |
| Probephase       | `TrialPeriodRecord`, `TrialPeriodStatus`                                       |
| Vertrag          | `ContractRecord`, `ContractVersionRecord`, `ContractStatus`                    |
| Dokumente        | `DocumentMetadata`, `DocumentType`                                             |
| Abo              | `SubscriptionRecord`, `SubscriptionPlanRecord`, `SubscriptionStatus`           |
| Steuer           | `TaxProfileRecord`, `TaxCustomerType`, `DE_VAT_RATE_STANDARD`                  |
| Rechnung         | `InvoiceRecord`, `InvoiceLineRecord`, `InvoiceStatus`, `InvoiceLineType`       |
| Zahlung          | `PaymentEventRecord`, `PaymentMethodRef`, `PaymentEventType`                   |
| Konten Demo/Live | `WalletAccountRecord`, `WalletKind`                                            |
| Boerse           | `ExchangeConnectionRecord`, `ExchangeConnectionMode`, `ApiCredentialRefRecord` |
| Telegram         | `TelegramLinkRecord`, `TelegramLinkStatus`                                     |
| Trading          | `OrderRecord`, `TradeFillRecord`, `OrderWalletKind`, `OrderStatus`             |
| Performance      | `PerformancePeriodRecord`, `ProfitShareRuleRecord`, `ProfitShareAccrualRecord` |
| Freigaben        | `ApprovalRecord`, `ApprovalType`, `RestrictionRecord`                          |
| Audit / Support  | `AuditLogEntry`, `SupportNoteRecord`                                           |

---

## Status und Pflichtfelder

Siehe Feld `model_config` und Kommentare in `commercial_data_model.py`. **Rechnungen** nach
`ISSUED` fachlich **unveraenderbar** (Storno ueber neue Vorgaenge).

---

## Steuer

Regelsteuersatz Deutschland (Standardware/Leistung): **19 %** als `DE_VAT_RATE_STANDARD`.
**Endgueltige** steuerliche Einordnung (Kleinunternehmer, Reverse Charge, B2B EU) — **Steuerberater**.

---

## Beziehungen

`customer_account_id` verknuepft die meisten Entitaeten. **Secrets** nur als Referenz
(`secret_store_key`), nie Klartext in diesen Modellen.

---

## Verweise

- `shared_py.customer_lifecycle` — Phasen und Gates
- `shared_py.product_policy` — Ausfuehrungsmodus Demo/Live
