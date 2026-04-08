# Kommerzieller Vertragsworkflow (Prompt 12)

## Datenmodell

- Migration `608_commercial_contract_workflow.sql`: `app.contract_template`, `app.tenant_contract`, `app.tenant_contract_document` (append-only, `draft_pdf` / `signed_pdf`), `app.contract_review_queue`.
- Maximal eine „offene“ Vertragsinstanz pro Tenant (partieller Unique-Index auf Status).

## API-Gateway

| Pfad                                                         | Zweck                                                                                                                                                                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/commerce/customer/contracts/templates`              | Aktive Vorlagen                                                                                                                                                                                               |
| `GET /v1/commerce/customer/contracts`                        | Instanzen + letzte Queue-Hinweise                                                                                                                                                                             |
| `POST /v1/commerce/customer/contracts/start`                 | Body: `{"template_key","template_version"?}` — nur bei Lifecycle `contract_pending`                                                                                                                           |
| `GET /v1/commerce/customer/contracts/{id}`                   | Detail                                                                                                                                                                                                        |
| `GET /v1/commerce/customer/contracts/{id}/documents`         | Metadaten                                                                                                                                                                                                     |
| `GET .../documents/{document_id}/download`                   | PDF (`application/pdf`)                                                                                                                                                                                       |
| `POST .../signing-session`                                   | Mock-Envelope (`provider=mock`)                                                                                                                                                                               |
| `POST .../mock-complete-sign`                                | Nur wenn `COMMERCIAL_CONTRACT_ALLOW_MOCK_CUSTOMER_COMPLETE=true` und nicht Production                                                                                                                         |
| `GET /v1/commerce/admin/contracts/review-queue`              | Admin (`billing:admin`)                                                                                                                                                                                       |
| `PATCH /v1/commerce/admin/contracts/review-queue/{queue_id}` | Status, interne Notizen, Kundenhinweis; bei `approved_contract` → Vertrag `admin_review_complete`                                                                                                             |
| `POST /v1/commerce/webhooks/contract-esign`                  | Öffentlich per Secret: Header `X-Commercial-Contract-Signature` = HMAC-SHA256(hex) über kanonisches JSON (`sort_keys=true`, `separators=(",", ":")`), identisch zu `api_gateway.esign_mock.sign_webhook_body` |

## Lifecycle

- Nach erfolgreicher Signatur (Webhook oder Dev-Mock): `tenant_contract.status` → `signed_awaiting_admin`, `signed_pdf` speichern, Review-Queue `pending_review`, optional `transition_lifecycle` mit `TransitionActor.SYSTEM` von `contract_pending` → `contract_signed_waiting_admin`.
- `POST /v1/commerce/customer/lifecycle/ack-contract-signed` ist gesperrt, wenn `commercial_contract_stub_ack_disabled()` (siehe `GatewaySettings`): erzwungenes Signing-Workflow-Flag oder Production mit konfiguriertem Webhook-Secret.

## Dashboard

- Kundenbereich: `/console/account/contract` (BFF: `GET/POST /api/dashboard/gateway/v1/commerce/customer/contracts/...`, PDF-Binary über erweiterten Gateway-GET-Proxy).

## Konfiguration

Siehe `.env.example`: `COMMERCIAL_CONTRACT_*`.
