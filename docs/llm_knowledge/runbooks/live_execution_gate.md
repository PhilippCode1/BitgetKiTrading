# Live-Execution-Gate (Kurzfassung)

- Live-Orders nur mit explizitem Operator-Gate (`EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE`, funktionsfähiger Live-Broker).
- Allowlisten: Symbole, Marktfamilien und Produkttypen müssen zur Bitget-Metadatenlage passen — keine erfundenen Instrumente.
- Shadow/Paper dienen Parität und Lernen; Abweichungen können Live-Kandidaten blockieren, wenn konfiguriert.
- Der LLM-Orchestrator führt **keine** Orders aus und ändert **keine** Strategieparameter.
