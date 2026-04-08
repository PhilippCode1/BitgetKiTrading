# Regime-Engine (kanonisch, `shared_py.regime_engine`)

## Version

- **`REGIME_ENGINE_VERSION`** (z. B. `3.0.1`) steht in jedem `regime_snapshot` unter `source_snapshot_json` bzw. in der Snapshot-Map.
- Aenderungen an Schwellen oder Prioritaeten → Minor-Bump der Engine-Version; Retrain von `market_regime_classifier` und Abgleich der Feature-Vector-Version (`SIGNAL_MODEL_FEATURE_SCHEMA_VERSION`).

## Regime (Hauptzustaende)

| Regime          | Kurzbeschreibung                                                                                                     |
| --------------- | -------------------------------------------------------------------------------------------------------------------- |
| **trend**       | Struktur UP/DOWN, wenig CHOCH-Churn, MTF-Alignment ≥ 0.5, kein dominierender Range-Score.                            |
| **chop**        | Range/CHOCH/Fake-Breakout — Seitwaerts oder noisy; Default wenn keine hoehere Prioritaet greift.                     |
| **compression** | `compression_flag` oder enge Range (range_score + niedriges atrp) mit Box-Hinweis.                                   |
| **breakout**    | Frisches `BREAKOUT`-Event im TF-Fenster, kein gleichzeitiges `FALSE_BREAKOUT`.                                       |
| **shock**       | News-Schock (Relevanz/Sentiment/Fenster) — mit oder ohne Mikrostruktur-Bestaetigung.                                 |
| **dislocation** | Mikrostruktur-Stress **ohne** aktiven News-Schock: genug parallele Stress-Signale (Vol, Spread, Costs, OI, Funding). |

## Regime-State (feingranular, family-aware)

Zusaetzlich zu `market_regime` fuehrt die Engine einen **`regime_state`** fuer Routing, Playbook-Zulassung und Audit:

| Regime-State           | Kurzbeschreibung                                                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **trend**              | Struktur-/MTF-getriebener Trendkontext (entspricht typischerweise `market_regime=trend`).                                                                                             |
| **mean_reverting**     | Ruecklauf-/Fade-Kontext mit hoher Mean-Reversion-Pressure, Range-Charakter oder wiederholtem CHOCH-Churn unter `market_regime=chop`.                                                  |
| **compression**        | Verdichtung / Pre-Break (typischerweise `market_regime=compression`).                                                                                                                 |
| **expansion**          | Ausbruchs-/Impulsfolge (typischerweise `market_regime=breakout` oder starker Impulscluster).                                                                                          |
| **news_driven**        | Relevante News ohne harten News-Shock-Schwellenpfad.                                                                                                                                  |
| **shock**              | News-Shock-Pfad (typischerweise `market_regime=shock`).                                                                                                                               |
| **low_liquidity**      | Spread/Execution/Depth/Orderbook-Kontext signalisiert duenne Liquiditaet (kann parallel zu `market_regime=dislocation` auftreten — Stack wird im `regime_substate` explizit benannt). |
| **delivery_sensitive** | Futures: nahes Zeitfenster (Funding/Roll/Event-Distanz).                                                                                                                              |
| **funding_skewed**     | Futures: Funding/Basis-Skew als dominanter Kontext.                                                                                                                                   |
| **session_transition** | Session-Open-/Hourly-Fenster mit erhoehter Repricing-Wahrscheinlichkeit.                                                                                                              |
| **range_grind**        | Balance-/Range-Grind ohne echte Trendexpansion.                                                                                                                                       |

Die deterministische Policy und Hashes liegen in `shared_py.regime_policy` (`REGIME_ROUTING_POLICY_VERSION`, `REGIME_POLICY_HASH`).

## Uebergaenge (Hysterese)

`regime_transition_state` und `regime_persistence_bars` verhindern unkontrolliertes Flattern:

- **stable**: effektiver `regime_state` entspricht dem Rohkandidaten in Folgebars.
- **entering**: Kandidatenwechsel erkannt, aber noch nicht bestaetigt (Quality/Confidence-Gates).
- **switch_confirmed**: zweite konsistente Bestaetigung bei ausreichender `regime_confidence_0_1`.
- **sticky_hold**: bei fragiler Datenlage bleibt der vorherige Zustand aktiv.
- **switch_immediate**: harte Zustaende (z. B. Shock/Liquiditaet/Delivery) duerfen sofort umschalten.

## Unterzustaende (`regime_substate`)

Nur erklaerend, im Snapshot gespeichert, kein separates DB-Pflichtfeld. Beispiele: `breakout_fresh`, `chop_choch_churn` (Grob-Regime), `mean_reverting_choch_churn` (Fein-State), `low_liquidity_dislocation_stack`, `shock_news_led_micro`, `dislocation_liquidity_microstructure`, `trend_mtf_aligned`.

## Eingaben (kombinierte Signale)

- **Preis/Struktur**: `structure_state` (`trend_dir`, `compression_flag`, `breakout_box_json`), Structure-Events (`BREAKOUT`, `FALSE_BREAKOUT`, `CHOCH`) mit Alter relativ zu `analysis_ts_ms` und TF-Fenster (3× Barlaenge).
- **Volatilitaet / Range**: `range_score`, `atrp_14`, `vol_z_50`, `ret_1`, `impulse_body_ratio`, `confluence_score_0_100`.
- **Orderbuch / Execution**: `spread_bps`, `execution_cost_bps`, `volatility_cost_bps` (aus Primary-Feature-Zeile).
- **Funding / OI**: `funding_rate_bps`, `open_interest_change_pct`.
- **News**: `relevance_score`, `sentiment` (Text/Float), `impact_window` — Schock nur bei erlaubtem Fenster.

Konstanten und Schwellen: siehe `shared_py/regime_engine.py` (Kommentar „bewusst konservativ“).

## Training und Inferenz — Paritaet

- **Online**: `signal_engine.scoring.regime_classifier.classify_market_regime` baut `RegimeEngineInputs` aus `ScoringContext` und ruft **`shared_py.regime_engine.classify_regime`** auf.
- **Offline**: Dieselbe Funktion mit **denselben** Eingaben (Features, Events, News-Zeile, `analysis_ts_ms`, `timeframe`) liefert **identische** `market_regime`, Bias, Confidence, Reasons und Snapshot.
- Gespeicherte Evaluationszeilen enthalten das zum Entscheidungszeitpunkt berechnete `market_regime` im Signal-Snapshot; Replays sollten, wenn moeglich, **vollstaendige** Structure-Events nutzen (nicht nur `structure_snapshot_json`-Stichprobe), sonst kann das Replay vom Live-Wert abweichen.

## Grenzen

- Liquidations- und Margin-Logik sind **nicht** Teil der Regime-Engine.
- Schwellen sind heuristisch; keine garantierte Kalibrierung auf alle Maerkte.
- News-Schock kann ohne starke Mikrostruktur ausloesen (bewusstes „Event-Risiko“).
- `dislocation` ersetzt nicht die Risiko-Pipeline — es klassifiziert Markt**zustand**, nicht Order-Gates.

## Tests

- `tests/shared/test_regime_engine.py` — deterministische Umschlaege und Stressfaelle.
- `tests/signal_engine/test_regime_classifier.py` — Kontext der Signal-Engine.
