# Telegram / Chat-Grenzen (Vertrag v1)

- **Erlaubt:** Status lesen, Signal-/Strategie-**Erklaerungen** (read-only), Shadow/Paper/Live-Reviews, **explizite** Open-/Close-/Abort-/Emergency-Freigaben nur fuer **gebundene** Ressourcen (`execution_id`, `internal_order_id`), Ergebnis-/Nachbesprechungs-Feeds (`operator_intel`).
- **Verboten:** Strategie umschreiben, Modellgewichte, Playbooks, Risk-Grenzen, Registry-Promotions, Prompt-/Policy-Texte im Produktionskern aendern. Allowlist in `alert_engine.telegram.commands`; Verbots-Verben in `shared_py.telegram_chat_contract.FORBIDDEN_CHAT_STRATEGY_MUTATION_VERBS`.
- **Echtgeld:** Zweistufig (Pending + Code), optional **TELEGRAM_OPERATOR_ALLOWED_USER_IDS** und **TELEGRAM_OPERATOR_CONFIRM_TOKEN**; Audit `alert.operator_action_audit` mit `chat_contract_version`, `rbac_scope`, `manual_action_token_fp`. Parallel laufen Paper/Shadow; Operator-Aktionen **aendern keine** Strategie-Policy.
- **Unmanipulierbar** = Kern gegen Chat-Mutation geschuetzt; **Safety/Compliance** (Kill-Switch, Latch, Gateway-RBAC, Manual-Action-JWT) bleiben aktiv.
