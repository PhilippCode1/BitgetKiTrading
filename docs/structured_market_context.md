# Strukturierter Marktkontext (`structured_market_context`, smc-v1)

## Zweck

Kontext (News, Listings, Makro, Funding, Sessions, Strukturbrueche, Exchange-Status) wird **nicht** nur als
globales Sentiment aggregiert, sondern als **Facetten** mit **instrumentenspezifischer Gewichtung**,
**zeitlichem Decay**, **Surprise-Score** und **Konfliktregeln** gegen die technische Richtung ausgewertet.

- **Gleiche Analyse** fuer Shadow/Paper/Live (ein Snapshot, eine Berechnung).
- **Haertere Live-Drossel**: zusaetzliche Codes in `live_execution_block_reasons_json` (v. a.
  `context_live_event_surprise_escalation`, playbook-spezifisch `context_playbook_news_shock_live_escalation`),
  die der Live-Broker wie andere Portfolio-Live-Blocker behandelt.

Implementierung: `shared/python/src/shared_py/structured_market_context.py`, eingebunden in
`run_scoring_pipeline` (`service.py`), `apply_rejections`, `risk_governor` (Live-Liste), Playbook-Refinement
in `_apply_specialist_stack`.

## Facetten (`facets_active_json`)

Heuristisch aus News-Text + optional `raw_json.topic_tags` sowie Struktur-Events (CHOCH):

| Facette                 | Beispiel-Stichworte / Quelle            |
| ----------------------- | --------------------------------------- |
| `listing`               | listing, will list, notierung           |
| `delisting`             | delist, trading halt                    |
| `funding_settlement`    | funding rate, funding payment           |
| `delivery`              | delivery, contract expiry               |
| `session_open`          | market open, rth open, asia open        |
| `macro`                 | cpi, fomc, fed, inflation               |
| `benchmark_correlation` | btc dominance, risk-off                 |
| `exchange_status`       | outage, maintenance, withdrawal suspend |
| `structure_break`       | CHOCH in `structure_events`             |

## Instrumentenkontext (`instrument_context_key`)

Ableitung aus Symbol + `market_family`, z. B. `btc_futures`, `alt_spot`, `eth_margin`.
Facetten-Gewichte skalieren damit (Makro staerker fuer BTC-Futures, Listing staerker fuer Spot/Alts).

## Ausgabefelder (Kern)

| Feld                                | Rolle                                                                 |
| ----------------------------------- | --------------------------------------------------------------------- |
| `annotation_only_reasons_json`      | Nur Audit/Explain — **keine** Gates                                   |
| `deterministic_rejection_soft_json` | Downgrade-Pfad in `apply_rejections` (kein automatischer Hard-Reject) |
| `deterministic_rejection_hard_json` | Nur wenn `SMC_HARD_EVENT_VETO_ENABLED=true` — harte Vetos             |
| `live_execution_block_reasons_json` | **Nur Live-Execution** (zusaetzlich zu Risk-Governor Konto-Stress)    |
| `composite_effective_factor_0_1`    | Multiplikator auf Signal-Staerke nach Soft-Konflikten                 |
| `surprise_score_0_1`                | Relevanz x Decay x Sentiment x Impact-Window x Facetten-Dichte        |

## ENV (SignalEngineSettings)

| Variable                                    | Bedeutung                                                    |
| ------------------------------------------- | ------------------------------------------------------------ |
| `STRUCTURED_MARKET_CONTEXT_ENABLED`         | Master-Schalter                                              |
| `SMC_NEWS_DECAY_HALF_LIFE_MINUTES`          | Halbwertszeit fuer Relevanz-Decay                            |
| `SMC_SURPRISE_DIRECTIONAL_THRESHOLD_0_1`    | Schwelle Konflikt technisch vs. Event                        |
| `SMC_SURPRISE_LIVE_THROTTLE_THRESHOLD_0_1`  | Schwelle Live-Block `context_live_event_surprise_escalation` |
| `SMC_COMPOSITE_SHRINK_MIN_0_1`              | Untergrenze fuer Staerken-Shrink                             |
| `SMC_ENABLE_STRUCTURAL_BREAK_BOOST`         | CHOCH als Facette                                            |
| `SMC_HARD_EVENT_VETO_ENABLED`               | Optionale harte Vetos (Default **false**)                    |
| `SMC_HARD_EVENT_VETO_SURPRISE_0_1`          | Schwelle fuer Vetos                                          |
| `SMC_PLAYBOOK_NEWS_SENSITIVE_SURPRISE_MULT` | Multiplikator bei news_shock / time_window                   |
| `SMC_PLAYBOOK_TREND_SURPRISE_MULT`          | Multiplikator Trend-Playbooks                                |

## Playbook-Nachverarbeitung

Nach `build_specialist_stack`: `refine_structured_market_context_for_playbook` passt Surprise an und kann
`context_playbook_news_shock_live_escalation` ergaenzen. `risk_governor` im Snapshot und `event_payload`
werden nachgetragen.

## Operator-Audit

- `reasons_json.structured_market_context_summary`
- `source_snapshot_json.structured_market_context` (voll)
- `decision_control_flow` Phase `hybrid_risk_leverage_meta` → `evidence.structured_market_context`
