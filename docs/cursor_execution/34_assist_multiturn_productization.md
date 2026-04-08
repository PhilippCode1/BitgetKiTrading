# 34 — Assist Multi-Turn: Segmentierung, Rechte, UX

## Ziel

Das **Assist-System** (Multi-Turn, Redis-Verlauf) soll klar in vier **Segmente** mit je eigener Rolle, Kontext-Allowlist und Gateway-Rechten arbeiten — **ohne Segmentvermischung**, **ohne implizite Freigabe** und mit **verständlicher Nutzererwartung** (Copy, Hilfetexte, Transcript).

Referenz: `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md`.

## Segmentmatrix

| Dashboard-UI                       | BFF-Segment (URL)     | Gateway-Pfad                                | `assist_role` (Orchestrator) | Auth (Gateway)           | Kontext-Allowlist (Top-Level-Keys, Auszug)                                                         |
| ---------------------------------- | --------------------- | ------------------------------------------- | ---------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------- |
| Health → Tab „Plattform & Betrieb“ | `admin-operations`    | `POST /v1/llm/assist/admin-operations/turn` | `admin_operations`           | `require_admin_read`     | `platform_health`, `signals_summary`, `orders_snapshot`, … siehe `shared_py/llm_assist_context.py` |
| Health → Tab „Strategie & Signale“ | `strategy-signal`     | `…/strategy-signal/turn`                    | `strategy_signal`            | `require_sensitive_auth` | `signal_snapshot`, `signal_history`, `risk_limits`, …                                              |
| Account → Tab „Einstieg & Profil“  | `customer-onboarding` | `…/customer-onboarding/turn`                | `customer_onboarding`        | `require_billing_read`   | `tenant_profile`, `trial_status`, `onboarding_checklist`, …                                        |
| Account → Tab „Rechnung & Vertrag“ | `support-billing`     | `…/support-billing/turn`                    | `support_billing`            | `require_billing_read`   | `tenant_billing_snapshot`, `invoices_summary`, `plan_snapshot`, …                                  |

**Defense in Depth:** Gateway ruft `filter_assist_context_payload` auf; Orchestrator erneut `filter_context_for_role` (`context_policy.py`).

## Konversations-Speicher (Redis) und Segment-Trennung

- **Implementierung:** `services/llm-orchestrator/src/llm_orchestrator/assist/conversation_store.py`
- **Redis-Key:** `llm:assist:v1:{partition}:{assist_role}:{conversation_id}`
- **Warum:** Zuvor teilten sich `customer_onboarding` und `support_billing` dieselbe Tenant-Partition bei gleicher `conversation_id` — potenziell **gemeinsamer Verlauf** trotz unterschiedlicher Segment-Prompts. Jetzt ist **`assist_role` fester Bestandteil des Keys**.
- **TTL / Kapazität:** `LLM_ASSIST_CONVERSATION_TTL_SEC` (Default 86 400 s), `LLM_ASSIST_MAX_HISTORY_MESSAGES` (Default 24) — `llm_orchestrator/config.py`.

**[TECHNICAL_DEBT]** Nach Deploy sind ältere Keys ohne `assist_role`-Segment im Pfad wirkungslos; Nutzer sehen leeren Verlauf bis zur nächsten Nachricht (akzeptabel für Kurzdialoge).

## UI-Pfade

| Seite   | Route (App)                            | Panel                          | Hinweise                                                              |
| ------- | -------------------------------------- | ------------------------------ | --------------------------------------------------------------------- |
| Health  | `console/health`                       | `AssistLayerPanel` — zwei Tabs | Lead + „Tab wechseln“-Hinweis; segment-spezifischer Kontext-Hilfetext |
| Account | `console/account` (`#customer-assist`) | `AssistLayerPanel` — zwei Tabs | Lead betont Trennung von Health-Assist und `billing:read`             |

**Tab-Wechsel im Browser:** Neuer Gesprächsverlauf in der Anzeige und **neue `conversation_id`**, damit Transcript und Serverzustand pro Segment konsistent bleiben.

## BFF

- Datei: `apps/dashboard/src/app/api/dashboard/llm/assist/[segment]/route.ts`
- **Segment-Allowlist:** `apps/dashboard/src/lib/assist-bff.ts` (`ASSIST_DASHBOARD_SEGMENTS`, `isAssistDashboardSegment`)
- **`conversation_id`:** strikte UUID-Prüfung (`isValidAssistConversationId`); bei Fehler **400** mit `detail.code: ASSIST_CONVERSATION_ID_INVALID`

## Tests (ausgeführt)

```text
# Repo-Root
python -m pytest tests/llm_orchestrator/test_assist_turn.py ^
  tests/unit/api_gateway/test_routes_llm_assist.py ^
  tests/llm_eval/test_eval_assist_cases.py -q --tb=short

# Dashboard
cd apps/dashboard
pnpm check-types
pnpm test -- src/lib/__tests__/assist-bff.test.ts --runInBand
```

**Ergebnis (lokaler Lauf):** 12 Pytest-Tests in den drei Dateien oben grün; `pnpm check-types` grün; Jest assist-bff grün.

**Neu / erweitert:**

- `test_assist_roles_do_not_share_redis_history` — gleiche `conversation_id` und Partition, zwei Rollen → zwei Redis-Keys.
- `test_filter_assist_context_unknown_role_raises`
- `tests/unit/api_gateway/test_routes_llm_assist.py` — Forward, Kontext-Filter, ungültige UUID, unbekanntes Segment 404
- `apps/dashboard/src/lib/__tests__/assist-bff.test.ts` — Segmentliste und UUID-Validierung

## Nachweis Health- und Account-Assist (manuell)

1. **Health:** `/console/health` — Bereich „Assistenzschicht“: Tab Plattform vs. Strategie, optional JSON-Kontext mit erlaubten Keys, Senden, Transcript zeigt aktives Segment.
2. **Account:** `/console/account` — Abschnitt Kunden-Assist (`#customer-assist`): Tabs Einstieg vs. Rechnung, gleicher Ablauf.
3. Tab wechseln: Verlauf leert sich, neue Konversations-ID (Präfix in der UI).

## Geänderte / neue Dateien (Überblick)

| Bereich            | Pfad                                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Conversation-Store | `services/llm-orchestrator/src/llm_orchestrator/assist/conversation_store.py`                                                                           |
| Service            | `services/llm-orchestrator/src/llm_orchestrator/service.py`                                                                                             |
| BFF-Helfer         | `apps/dashboard/src/lib/assist-bff.ts`                                                                                                                  |
| BFF-Route          | `apps/dashboard/src/app/api/dashboard/llm/assist/[segment]/route.ts`                                                                                    |
| UI                 | `apps/dashboard/src/components/panels/AssistLayerPanel.tsx`                                                                                             |
| Seiten             | `health/page.tsx`, `account/page.tsx`                                                                                                                   |
| i18n               | `apps/dashboard/src/messages/de.json`, `en.json`                                                                                                        |
| Tests              | `tests/llm_orchestrator/test_assist_turn.py`, `tests/unit/api_gateway/test_routes_llm_assist.py`, `apps/dashboard/src/lib/__tests__/assist-bff.test.ts` |

## Offene Punkte

- **[FUTURE]** Dedizierte `resolveAssistFailure`-Funktion (statt Operator-Explain-Mapping) für 422 `ASSIST_CONTEXT_INVALID` und BFF `ASSIST_CONVERSATION_ID_INVALID`.
- **[RISK]** In Produktion mit erzwungenem Gateway-Auth müssen JWT-Rollen zu den Segment-Endpunkten passen — siehe Matrix oben.
