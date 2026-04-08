# Modellschicht: Datenvertrag (Training & Inferenz)

## Ueberblick

Die Modellschicht nutzt zwei zusammenpassende Ebenen:

1. **Feature-Snapshot** (`schema_kind: model_feature_snapshot` in `shared_py.model_contracts`): Roh- und normalisierte Marktmerkmale pro Timeframe, inkl. `feature_schema_version` / `feature_schema_hash`.
2. **Signal-Modell-Feature-Vektor** (`schema_kind: signal_model_feature_vector` in `shared_py.take_trade_model`): fester, sortierter Float-Vektor aus Signal-Snapshot + Feature-Snapshot fuer Meta-Modelle (z. B. `take_trade_prob`).

Die **Modellschicht-Gesamtversion** ist `MODEL_LAYER_CONTRACT_VERSION` in `shared_py.model_layer_contract`. Der **Feldkatalog** (Pflicht / optional / experimentell) ist separat mit `FIELD_CATALOG_VERSION` und `FIELD_CATALOG_HASH` versioniert; der bestehende `SIGNAL_MODEL_FEATURE_SCHEMA_HASH` (nur Feldliste) bleibt unveraendert, damit aeltere Artefakte weiter erkennbar sind.

Seit dem family-aware Feature-Snapshot (`FEATURE_SCHEMA_VERSION = 3.0`) traegt
bereits der Roh-Snapshot selbst einen separaten Feldkatalog:

- `FEATURE_FIELD_CATALOG_VERSION`
- `FEATURE_FIELD_CATALOG_HASH`
- Gruppen `identity`, `core`, `microstructure`, `family`, `quality`

Dadurch bleibt der Snapshot fuer Training und Inferenz einfrierbar, ohne jede
Dokuaenderung am Modellvektor zu einem Hash-Bruch des eigentlichen
`SIGNAL_MODEL_FEATURE_SCHEMA_HASH` zu machen.

Seit dem Playbook-Schritt traegt auch der Signal-Output eine explizite,
versionierte Playbook-Bindung:

- `playbook_id`
- `playbook_family`
- `playbook_decision_mode`
- `playbook_registry_version`

Der volle Fachkontext lebt bewusst **nicht** als weitere starre Top-Level-Liste
im Modellvektor, sondern als versioniertes Sidecar:

- `build_model_contract_bundle()["playbook_registry"]`
- `source_snapshot_json.playbook_context`
- `reasons_json.playbook`

So bleibt Training-/Inference-Paritaet sauber, waehrend die Entscheidung
trotzdem an eine registrierte Playbook-Familie oder eine explizite
`playbookless`-Begruendung gebunden werden kann.

## Kanonisches Feature-Schema (Vektor)

- **Reihenfolge**: exakt `SIGNAL_MODEL_FEATURE_FIELDS` / `TAKE_TRADE_FEATURE_FIELDS` in `take_trade_model.py`.
- **Training**: identische Spaltenreihenfolge wie Inferenz (`training_feature_matrix` in `training_dataset_builder.py`).
- **Metadaten**: `canonical_model_layer_descriptor()` liefert gebundelte Versionen und Hashes fuer Manifeste und Debugging.

## Feature-Snapshot vor dem Vektor

Der Roh-Snapshot ist jetzt family-aware und traegt unter anderem:

- `canonical_instrument_id`, `market_family`, `product_type`, `margin_account_mode`
- Futures-only Felder wie `mark_index_spread_bps`, `basis_bps`,
  `funding_time_to_next_ms`, `liquidation_distance_bps_max_leverage`
- Quality-Felder wie `data_completeness_0_1`, `staleness_score_0_1`,
  `gap_count_lookback`, `feature_quality_status`

Missing-Value-Semantik:

- `source=not_applicable`: Feld fachlich ungueltig fuer die Family
- `source=missing`: Feld waere sinnvoll, war aber as-of nicht vorhanden
- `market_family=unknown`: nur Legacy-/Alt-Snapshot-Normalisierung; neuer
  Produktionspfad soll echte Instrument-Identitaet liefern

## Pflicht, optional, experimentell

Quelle der Wahrheit: `shared_py.model_layer_contract` (`_OPTIONAL_SIGNAL_FIELDS`, `_EXPERIMENTAL_SIGNAL_FIELDS`; alle uebrigen Vektorfelder sind **required**).

| Tier             | Bedeutung im Training-Builder                                                    |
| ---------------- | -------------------------------------------------------------------------------- |
| **required**     | Zeile wird verworfen, wenn der Wert fehlt oder nicht endlich ist (NaN/Inf).      |
| **optional**     | Fehlende Werte (NaN) sind zulaessig; Modell (z. B. HGB) kann NaN verarbeiten.    |
| **experimental** | Ebenfalls NaN-zulaessig; fuer Produktions-Gates nicht als Kernannahme verwenden. |

### Experimentell (Auszug)

`news_score_0_100`, `history_score_0_100`, `impulse_upper_wick_ratio`, `impulse_lower_wick_ratio`, `depth_to_bar_volume_ratio`, `impact_*`, `execution_cost_bps`, `volatility_cost_bps`, `funding_cost_bps_window`, `open_interest_change_pct`.

### Optional (Auszug)

`atrp_14`, `structure_score_0_100`, `momentum_score_layer_0_100`, `multi_timeframe_score_0_100`, `risk_score_0_100`, `weighted_composite_score_0_100`, `reward_risk_ratio`, `expected_volatility_band`, `regime_confidence_0_1`, `momentum_score_feature`, `impulse_body_ratio`, `vol_z_50`, `spread_bps`, `depth_balance_ratio`, `funding_rate_bps`, `trend_slope_proxy`, `confluence_score_0_100`, `range_score`, `trend_dir_*` (je TF), `high_tf_alignment_ratio`.

Vollstaendige Zuordnung: `build_signal_field_catalog()` bzw. `canonical_model_layer_descriptor(include_field_tiers=True)`.

## Dataset-Builder

`shared_py.training_dataset_builder.build_take_trade_training_dataset`:

- **Zeitbezug**: `feature_snapshot_asof_ms` aus `primary_tf.computed_ts_ms` vs. `decision_ts_ms`.
- **Freshness**: Verwerfen, wenn `decision_ts_ms - asof_ms > max_feature_age_ms` (konfigurierbar; Standard an `LEARN_MAX_FEATURE_AGE_MS` der Learning-Engine gekoppelt).
- **Leakage (Zukunft)**: Verwerfen, wenn `asof_ms > decision_ts_ms + future_feature_slack_ms`.
- **Leakage (Modell-Outputs im Signal-Snapshot)**: Schluessel in `LEAK_PRONE_SIGNAL_SNAPSHOT_KEYS` mit „informativen“ Werten (nicht `None`, nicht leere Liste, nicht boolesch `False`) fuehren zum Drop.
- **Schema-Drift**: fehlende oder zusaetzliche Schluessel im Feature-Dict → Drop, Stichproben in `schema_drift_samples` im Trainings-Metadaten-Report.
- **Reproduzierbarkeit**: `take_trade_dataset_config_fingerprint` und `drop_counts` gehen in `dataset_hash` / Manifest-`extra` ein.

## Tests

- `tests/shared/test_model_layer_contract.py` — Katalogabdeckung, Descriptor, Drift-Erkennung, Leak-Audit.
- `tests/shared/test_training_dataset_builder.py` — Gates (stale, future, leak) und As-of-Extraktion.
