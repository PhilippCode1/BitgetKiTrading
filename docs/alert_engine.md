# Alert-Engine (Prompt 27)

## Architektur

Kanonische Statusbegriffe fuer Operatoren und Freigaben: `docs/operator_status_language.md`.

1. **Redis Consumer Group** (`alert-engine`) liest parallelisiert aus:
   - `events:signal_created`, `events:structure_updated`, `events:trade_closed`,
   - `events:risk_alert`, `events:news_scored`, `events:system_alert`,
   - `events:operator_intel` (strukturierter Operator-Feed: Intents, No-Trade, Execution, Exits; **keine** Strategie-Mutation)
2. **Policy Engine** (deterministisch V1) erzeugt `AlertIntent`-Kandidaten.
3. **Dedupe** über Tabelle `alert.dedupe_keys` (TTL in Minuten, konfigurierbar).
4. **Outbox** `alert.alert_outbox`: pro Ziel-Chat eine Zeile, Zustände `pending → sending → sent|failed|simulated`.
5. **Sender-Worker** wendet globales und pro-Chat Rate-Limit an, ruft Telegram `sendMessage` auf (oder simuliert bei `TELEGRAM_DRY_RUN=true`).
6. **Telegram Ingress**:
   - `getUpdates` mit persistiertem `offset` in `alert.bot_state`, oder
   - `POST /telegram/webhook` mit Header `X-Telegram-Bot-Api-Secret-Token` und `TELEGRAM_WEBHOOK_SECRET`

### Long Polling vs. Webhook

- **Default: Long Polling** — kein öffentlicher Ingress nötig, gut für Dev/Docker.
- **Webhook:** `TELEGRAM_MODE=webhook` ist jetzt als Eingangspfad im Service implementiert. Der Bot-Provider muss extern auf `POST /telegram/webhook` zeigen; der Service validiert `TELEGRAM_WEBHOOK_SECRET`, verarbeitet den Update-Payload aber weiterhin nur ueber die bestehenden, read-only Chat-Kommandos.

## Policies V1

| Event                                                                          | Alert-Typ                           | Dedupe                                                  |
| ------------------------------------------------------------------------------ | ----------------------------------- | ------------------------------------------------------- |
| Signal `gross` oder Stärke ≥ `ALERT_SIGNAL_GROSS_THRESHOLD`                    | `GROSS_SIGNAL`                      | `gross:symbol:tf:bucket` (10-Min-Bucket)                |
| Sonst `kern` oder Stärke ≥ `ALERT_SIGNAL_CORE_THRESHOLD`                       | `CORE_SIGNAL`                       | analog                                                  |
| `structure_updated`: CHOCH-Flag oder Trendwechsel vs. DB-State                 | `TREND_WARN`                        | 10-Min-Bucket                                           |
| `trade_closed`                                                                 | `TRADE_CLOSED`                      | keins (Rate-Limit schützt)                              |
| `risk_alert`                                                                   | `STOP_DANGER`                       | keins                                                   |
| `news_scored`: Score ≥ `ALERT_NEWS_THRESHOLD` und `impact_window == immediate` | `NEWS_HIGH`                         | 30-Min-Bucket                                           |
| `system_alert`                                                                 | `SYSTEM_ALERT`                      | optional via Payload `dedupe_key`                       |
| `operator_intel`                                                               | `OPERATOR_*` (je nach `intel_kind`) | optional `dedupe_key` + `dedupe_ttl_minutes` im Payload |

## Operator-Intel (`events:operator_intel`)

- **Zweck:** Durchgehende, **rein informative** Telegram-Mitteilungen (Outbox) zu Strategiekontext, No-Trade, Freigabe-/Plan-Zusammenfassung, Ausführung, Exits und Reviews. Inhalte werden in `shared_py.operator_intel` **redacted** (keine Secrets, keine rohen Prompts).
- **Kanonische Nachrichtentypen (`intel_kind` → Outbox `alert_type`):** u. a. `pre_trade_rationale` → `OPERATOR_PRE_TRADE`, `release_pending` → `OPERATOR_RELEASE_PENDING`, `trade_open` / `trade_close` → `OPERATOR_TRADE_OPEN` / `OPERATOR_TRADE_CLOSE`, `exit_rationale` / `exit_result` → `OPERATOR_EXIT`, `post_trade_review` → `OPERATOR_POST_TRADE`, `incident` → `OPERATOR_INCIDENT`, `safety_latch` → `OPERATOR_SAFETY_LATCH`, `kill_switch` → `LIVE_BROKER_KILL_SWITCH`; bestehende `strategy_intent`, `plan_summary`, `execution_update`, … bleiben gueltig. Mapping: `alert_engine.alerts.policies._INTEL_KIND_ALERT`. Vertrags-Metadaten: `shared_py.telegram_chat_contract`.
- **Produzenten (opt-in):** `signal-engine` (`SIGNAL_OPERATOR_INTEL_OUTBOX_ENABLED`), `live-broker` (`LIVE_OPERATOR_INTEL_OUTBOX_ENABLED`). Beide publizieren nur bei explizitem Flag.
- **Nachrichtenlayout:** Kanonisches `payload.text` plus strukturierte Felder (`intel_kind`, `symbol`, `market_family`, `playbook_id`, `specialist_route`, `regime`, `risk_summary`, `stop_exit_family`, `leverage_band`, `reasons`, `outcome`, Referenzen wie `signal_id` / `execution_id`).
- **Threading / Verknüpfung:** Nach erfolgreichem Telegram-Versand schreibt der Outbox-Sender `SETEX ae:opintel:thread:{correlation_id} -> telegram_message_id` (TTL `TELEGRAM_OPERATOR_THREAD_TTL_SEC`). Folge-Events mit derselben `correlation_id` und ohne explizites `reply_to_telegram_message_id` nutzen den Anker als `reply_to_message_id` (erstes Chunk).
- **Rate Limits & Fehler:** Globales Send-Limit (`TELEGRAM_SEND_MAX_PER_SEC`, `TELEGRAM_SEND_MAX_PER_MIN_PER_CHAT`), Retries auf Transport-Ebene (`TELEGRAM_SEND_MAX_RETRIES`). Outbox-Zeilen: bei Fehlschlag **requeue** mit steigendem Versuchszähler bis `TELEGRAM_OUTBOX_MAX_SEND_ATTEMPTS`, danach `failed` (kein stilles Verlusten ohne Endzustand).
- **DB:** Migration `infra/migrations/postgres/580_alert_operator_intel_types.sql` erweitert `alert.alert_outbox.alert_type` für die `OPERATOR_*`-Typen.

## Security / Zugriffskontrolle

- `TELEGRAM_ALLOWED_CHAT_IDS`: explizite Whitelist. Ist sie **nicht leer**, werden alle anderen Chats ignoriert (Audit `ignored_not_whitelisted`).
- Ist sie **leer**: `/start` legt `pending` an; Admin muss `POST /admin/chats/{id}/allow` aufrufen.
- **ADMIN_TOKEN** nur serverseitig; niemals in `NEXT_PUBLIC_*` oder Logs.
- **Replay-/Admin-Pfade** verlangen `X-Admin-Token`; bei gesetztem `INTERNAL_API_KEY` zusaetzlich `X-Internal-Service-Key`.
- `POST /admin/replay-event` und `POST /admin/replay-telegram` bleiben ausserhalb lokaler/Test-Profile standardmaessig deaktiviert (`SECURITY_ALLOW_ALERT_REPLAY_ROUTES=false` in Shadow/Prod).

### Telegram: keine Strategie-Manipulation

- **Allowlist:** Nur dokumentierte Befehle werden akzeptiert. Jeder andere `/`-Befehl endet mit Hinweis an den Nutzer und zweifacher Protokollierung: `alert.command_audit` (`rejected_forbidden_command`) und `alert.operator_action_audit` (`rejected_forbidden_command`). Es gibt **keinen** freien Parser fuer Strategie-, Playbook-, Gewichts- oder Risk-Parameter.
- **Lesend / Benachrichtigung:** `/status`, `/mute`, `/unmute`, `/lastsignal`, `/lastnews`, `/help`.
- **Operator-Pfad (opt-in `TELEGRAM_OPERATOR_ACTIONS_ENABLED`):** zweistufige Freigaben mit Pending-Zeile in `alert.telegram_operator_pending`, Bestaetigungscode und TTL (`TELEGRAM_OPERATOR_CONFIRM_TTL_SEC`). Upstream nur ueber `ALERT_ENGINE_LIVE_BROKER_BASE_URL` mit `X-Internal-Service-Key` (`INTERNAL_API_KEY`).
- **`operator_release` / Mirror-Freigabe:** nur fuer **existierende** `execution_id` mit `live_candidate_recorded` + `effective_runtime_mode=live` und ohne bestehendes Release (siehe `GET /live-broker/executions/{id}/telegram-summary`). Keine freien Wunsch-Orders aus Telegram.
- **Notfall `emergency_flatten`:** nur mit **existierender** `internal_order_id` (UUID), ebenfalls zweistufig; keine Symbol-freiform ohne gebundene Order.
- **Revisionssicherheit:** `alert.operator_action_audit` protokolliert u. a. `pending_created`, `executed_ok`, `executed_error`, Ablehnungen (`rejected_*`, inkl. `rejected_rbac`, `rejected_manual_token`). Spalten **`chat_contract_version`**, **`rbac_scope`**, **`manual_action_token_fp`** (nur Fingerprint, kein Klartext-Token). Migrationen: `581_alert_telegram_operator_governance.sql`, `592_telegram_chat_contract_audit.sql`.
- **`GET /health`:** liefert `telegram_chat_contract` (Allowlists, Verbots-Verben, `contract_version`) aus `command_contract_summary()`.
- **Paritaet Dashboard:** Dieselbe inhaltliche Zweistufigkeit fuer Live-Broker-Mutationen laeuft ueber das API-Gateway (`POST /v1/auth/manual-action/mint` + `X-Manual-Action-Token`), siehe `docs/api_gateway_security.md`.

## Datenbank

Migration: `infra/migrations/postgres/230_alert_engine.sql` — Schema `alert`.

## Observability

- Logs: `policy matched: …`, `outbox inserted`, `SIMULATED SEND …`
- Produktionslogs nutzen redigierte Chat-/User-Referenzen und keine rohen Dedupe-Keys; tiefe Operator-Audits bleiben in `alert.operator_action_audit` / `alert.telegram_operator_pending`.
- `GET /health`: DB/Redis, `dry_run`, `last_update_id`, `outbox_pending`

## Nicht implementiert / spätere Erweiterungen

- Reicheres HTML/MarkdownV2-Formatting mit strikter Entity-Längen-Validierung.
- Quiet-Hours (zeitbasiert) zusätzlich zu `/mute`.
