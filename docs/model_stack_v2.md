# Model-Stack v2 (End-to-End)

## Architektur-Ueberblick

**Kanonischer Zielzustand:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

Der produktive **Inferenz- und Entscheidungsstack** ist geschichtet; keine Schicht ersetzt die andere:

1. **Marktinventar & Instrumentvertrag** — `shared_py.bitget.discovery`, `shared_py.bitget.instruments` und der zentrale Instrumentenkatalog liefern das metadata-getriebene Inventar fuer `spot`, `margin`, `futures` und nur real exponierte weitere Kategorien.
2. **Marktdaten & Features** — `market-stream`, `feature-engine` (inkl. Microstructure), konsistente As-of-Semantik und Data-Quality-Gates (`docs/features.md`, `docs/microstructure.md`).
3. **Struktur & Drawings** — `structure-engine`, `drawing-engine` (`docs/structure.md`, `docs/drawings.md`).
4. **Signal-Engine (deterministischer Kern)** — Scoring, Regime, **Risk-Engine**, Uncertainty, Abstention, Hybrid-Policy, **Integer-Leverage 7..75** mit Caps; Family-/Regime-/Playbook-Spezialisten plus deterministischer Router/Arbitrator werden im Audit-Trace mitgefuehrt; Ausgabe u. a. in `app.signals_v1` (`docs/signal_engine.md`, `docs/scoring_model_v1.md`, `docs/signal_explanations.md`).
5. **Model Registry v2 / Learning** — Champion/Challenger, Kalibrierungspflicht optional; **einzige** produktive Modell-Run-Zuweisung pro `model_name`, wenn aktiviert (`docs/model_registry_v2.md`).
6. **Online-Drift (Live-Gate)** — materialisierter Zustand `learn.online_drift_state`; kann Live handelsrelevant drosseln (`docs/online_drift.md`).
7. **LLM-Orchestrator** — **unterstuetzend** (z. B. News-Zusammenfassung); **nicht** alleiniger Trading-Kern (`docs/llm_orchestrator.md`, `docs/news_engine.md`).

## Spezialisten-System

- **Family-Spezialisten**: unterscheiden `spot`, `margin` und `futures` ueber den kanonischen Instrumentvertrag und koennen family-spezifische Hard-Blocker setzen.
- **Regime-Spezialisten**: bauen auf der bestehenden Regime-Klassifikation auf und liefern den Marktmodus fuer Routing und Explain/Audit.
- **Playbook-Spezialisten**: ordnen die Entscheidung in deterministische Playbooks wie `trend_follow_continuation`, `breakout_prep`, `mean_reversion_unwind` oder `no_trade_event` ein.
- **Router/Arbitrator**: fasst Family-, Regime- und Playbook-Sicht zusammen und schreibt die Auswahl in den Signal-Trace (`source_snapshot_json.specialists`, Event-Payload `specialists`).
- **Hartherzige No-Trade-Logik** bleibt priorisiert: Spezialisten koennen einen Trade nie am Risk-/Hybrid-/Drift-Kern vorbei freischalten.

Die Spezialisten sind **kein zweites Trading-System** neben dem Kern, sondern eine deterministische Schichtung innerhalb des bestehenden `signal-engine`-Pfads.

## Registry v2 vs. Legacy

- **Quelle der Wahrheit** fuer produktive Modell-Runs: `MODEL_REGISTRY_V2_ENABLED=true` → Tabelle `app.model_registry_v2` und Learning-API; Details und Betriebsschritte: **`docs/model_registry_v2.md`**.
- Champion-Run muss zu Kalibrierungs- und Qualitaetsanforderungen passen, wenn `MODEL_CALIBRATION_REQUIRED=true`.

## Paper-, Shadow- und Live-Bezug

- **Paper:** gleiche Signal-Pipeline; Ausfuehrung ueber Paper-Broker, aber kataloggebunden statt an einzelnen Produktkonstanten (`docs/paper_broker.md`).
- **Shadow:** identische Entscheidungslogik, keine echten Live-Orders; Vergleich zu Live-Pfad ueber Live-Broker-/Monitor-Metriken (`docs/shadow_live_divergence.md`).
- **Live:** zusaetzlich harte ENV-Gates (`LIVE_TRADE_ENABLE`, `EXECUTION_MODE=live`) und Broker-Safety.

## Observability

- Signal-/Drift-/Queue-Metriken: Monitor-Engine + Prometheus (`docs/observability.md`).
- Dashboard Learning-Board und Operator-Cockpit: Champion-Slots und Kennzahlen (`docs/dashboard_operator.md`).

## Verwandte Dokumente

| Thema                         | Dokument                                                   |
| ----------------------------- | ---------------------------------------------------------- |
| Registry-DB und API           | `docs/model_registry_v2.md`                                |
| Hybrid & Uncertainty          | `docs/signal_engine.md`, Prompt-nahe Migrationskommentare  |
| Backtests / Replay            | `docs/backtesting_replay.md`, `docs/replay_determinism.md` |
| Research / Benchmark-Evidence | `docs/research_benchmarking.md`                            |
| Learning-Pipeline             | `docs/learning_engine_v1.md`, `docs/learning_feedback.md`  |
