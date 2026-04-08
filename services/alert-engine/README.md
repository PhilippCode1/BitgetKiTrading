# alert-engine

Microservice für **Alert-Policies**, **Outbox + Retry**, **Dedupe**, **Telegram** (Standard: Long Polling `getUpdates`).

## Schnellstart (lokal)

```bash
# Migration (Schema alert.*)
python infra/migrate.py

export DATABASE_URL=postgresql://...
export REDIS_URL=redis://localhost:6379
export TELEGRAM_DRY_RUN=true
export ADMIN_TOKEN=dev-only
pip install -e ".[dev]"
python -m alert_engine.main
```

Health: `GET http://localhost:8100/health`

## ENV (Auszug)

| Variable                                       | Bedeutung                                                                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `TELEGRAM_DRY_RUN`                             | `true`: keine echten `sendMessage`-Calls; Outbox → `simulated`                                                            |
| `TELEGRAM_BOT_TOKEN`                           | Bot-Token (nie loggen / committen)                                                                                        |
| `TELEGRAM_MODE`                                | `getUpdates` (Default) oder später `webhook`                                                                              |
| `TELEGRAM_ALLOWED_CHAT_IDS`                    | Komma-separierte Chat-IDs; leer = nur `/start` → `pending` bis Admin-Freigabe                                             |
| `ADMIN_TOKEN`                                  | Schützt `POST /admin/*`                                                                                                   |
| `ALERT_*_THRESHOLD` / `ALERT_DEDUPE_MINUTES_*` | Policy V1                                                                                                                 |
| `TELEGRAM_OPERATOR_ACTIONS_ENABLED`            | `false`: keine Live-Broker-Aktionen aus Telegram; `true` nur mit `ALERT_ENGINE_LIVE_BROKER_BASE_URL` + `INTERNAL_API_KEY` |
| `TELEGRAM_OPERATOR_CONFIRM_TTL_SEC`            | TTL fuer zweistufige Bestaetigung (60..3600)                                                                              |
| `TELEGRAM_OPERATOR_ALLOWED_USER_IDS`           | Optional: CSV Telegram-`user_id` fuer Operator-Befehle (RBAC)                                                             |
| `TELEGRAM_OPERATOR_CONFIRM_TOKEN`              | Optional: drittes Argument bei `release_confirm` / `emerg_confirm` (Manual-Action-Paritaet)                               |

Siehe `.env.example` im Repo-Root. **Telegram-/Chat-Vertrag:** `docs/telegram_chat_contract.md` und `docs/alert_engine.md`.

## Telegram

- **getUpdates** und **Webhook** schließen sich aus (Telegram Bot API).
- Updates werden serverseitig max. **24h** gehalten → `last_update_id` in `alert.bot_state` persistieren (implementiert).
- `sendMessage.text`: max. 4096 Zeichen nach Entity-Parsing → Trunkierung auf `TELEGRAM_MESSAGE_SAFE_LEN` (Default 3500) + Chunking.

## Admin-HTTP

- `POST /admin/chats/{id}/allow` | `block` — Header `X-Admin-Token`
- `POST /admin/test-alert` — Test-Outbox-Eintrag
- `POST /admin/replay-event` — JSON `EventEnvelope`
- `POST /admin/replay-telegram` — Fake Telegram `Update` JSON (Tests)

## Fixtures

```bash
python tools/publish_alert_fixtures.py --type gross_signal
```

Mindestens ein Chat mit `status=allowed` (z. B. via Admin-Endpoint), sonst keine Outbox-Zeilen.

## Tests

```bash
PYTHONPATH=services/alert-engine/src;shared/python/src python -m pytest tests/alert_engine -q
```

## Troubleshooting

- **Keine Outbox-Einträge:** Consumer-Group prüfen: `redis-cli XINFO GROUPS events:signal_created`
- **Telegram 401:** Token falsch oder DRY_RUN aus aber kein Token
- **Pending hängt:** Chat `muted` oder nicht `allowed`

Weitere Details: `docs/alert_engine.md`.
