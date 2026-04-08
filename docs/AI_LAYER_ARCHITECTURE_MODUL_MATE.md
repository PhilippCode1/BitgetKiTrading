# KI-Schicht: Architektur (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 3; Kanonischer Code: `shared_py.ai_layer_contract`

---

## Ziel

Eine **zentrale KI-Schicht** statt verstreuter LLM-Aufrufe: spaeter **starke OpenAI-Modelle** einbindbar,
waehrend **Fachlogik**, **Trading-Entscheidung**, **Ausfuehrung** und **Protokoll** klar getrennt bleiben.

**Bestehende Implementierung:** `services/llm-orchestrator` liefert strukturierte Inferenz, Cache, Retrieval
und Provenance (siehe `docs/llm_orchestrator.md`). Dieser Dienst bleibt **ohne Orderhoheit**.

---

## Sechs Schichten (Reihenfolge)

| Stufe | Name im Code (`PipelineStage`) | Inhalt                                                          |
| ----- | ------------------------------ | --------------------------------------------------------------- |
| 1     | `USER_REQUEST`                 | UI/Telegram → typisierte Eingaben                               |
| 2     | `DOMAIN_CONTEXT`               | Status, Limits, Demo/Live (keine Secrets in Prompts)            |
| 3     | `AI_INFERENCE`                 | Modellaufruf, Prompt-Registry-Version, optional Tools (spaeter) |
| 4     | `TRADING_POLICY`               | Deterministische Pruefung / Materialisierung des Befehls        |
| 5     | `EXECUTION`                    | Demo- oder Live-Broker, idempotent                              |
| 6     | `AUDIT_LOG`                    | Append-only Trace, Hashes, Modell, Ergebnis                     |

---

## Admin-Steuerung (Konzept)

- **Prompt-Registry:** Schluessel `PromptRegistryKey`, Versionen in DB, veroeffentlicht durch Super-Admin.
- **Modell-Routing:** Profile `ModelRoutingProfile` (Economy / Standard / Reasoning).
- **Guardrails:** Stufe `GuardrailLevel`, Tool-Allowlists spaeter am Gateway.

---

## Sicherheit und Fallback

- Keine **API-Secrets** in KI-Kontext.
- **Fallback** bei Provider-Ausfall: siehe `FallbackStrategy` in `ai_layer_contract.py`.
- **Rate Limits** und Token-Budgets: Richtwerte in `DEFAULT_RATE_LIMIT_POLICY` (Anpassung in Services).

---

## Offene Punkte

- Tool-Calling fuer ausgewaehlte interne Funktionen: Policy und Allowlist **noch** im Orchestrator
  konservativ halten (aktuell: kein Tool-Calling laut `docs/llm_orchestrator.md`).
- RAG ausserhalb `docs/llm_knowledge`: separates Konzept + Admin-Freigabe.

---

## Verweise

- `docs/llm_orchestrator.md` — Betriebsdienst
- `shared_py.product_policy` / `shared_py.customer_lifecycle` — kommerzielle Gates (nie vom Modell setzen)
