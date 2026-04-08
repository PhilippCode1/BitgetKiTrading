# Telegram- und Chat-Vertrag (`telegram-chat-contract-v1`)

Kanonische Konstante: `shared_py.telegram_chat_contract.TELEGRAM_CHAT_CONTRACT_VERSION`.

## Erlaubte Befehle (Allowlist)

| Gruppe                        | Befehle                                                                                                                                |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Session                       | `/start`                                                                                                                               |
| Lesend                        | `/help`, `/status`, `/mute [min]`, `/unmute`, `/lastsignal`, `/lastnews`                                                               |
| Operator (Flag + Live-Broker) | `/exec_recent`, `/exec_show`, `/release_step1`, `/release_confirm`, `/release_abort`, `/emerg_step1`, `/emerg_confirm`, `/emerg_abort` |

`release_*` und `emerg_*` erfordern `TELEGRAM_OPERATOR_ACTIONS_ENABLED=true` und valide Live-Broker-Ops-URL. Optional: `TELEGRAM_OPERATOR_ALLOWED_USER_IDS` (CSV), `TELEGRAM_OPERATOR_CONFIRM_TOKEN` (drittes Argument bei `*_confirm`).

## Explizit nicht erlaubt (Beispiele)

Verbots-Verben ohne `/` in `FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS` (u. a. `set_weight`, `playbook`, `risk_limit`, `registry_promote`, `prompt_edit`). Jeder andere `/`-Befehl: `rejected_forbidden_command`.

## Ausgehende Nachrichtentypen

`summarize` in `command_contract_summary()` und `CHAT_OUTBOUND_MESSAGE_TYPES`; Intel-Mapping in `alert_engine.alerts.policies._INTEL_KIND_ALERT` und Labels in `shared_py.operator_intel`.

## Audit (DB)

`alert.operator_action_audit`: `chat_contract_version`, `rbac_scope`, `manual_action_token_fp` (SHA-256-Prefix, kein Klartext). Outcomes u. a. `rejected_rbac`, `rejected_manual_token`. Migration `592_telegram_chat_contract_audit.sql`.

## Gateway-Paritaet

Manuelle Echtgeld-Mutationen uebers Dashboard: `docs/api_gateway_security.md` (Mint + `X-Manual-Action-Token`).
