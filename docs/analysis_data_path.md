# Analyse-Datenpfad (Family-, Capability-, Katalog-basiert)

## Ziel

Einheitlicher Pfad fuer **oeffentliche Marktdaten**, **family-spezifische Microstructure**
und **Derivat-Kontext** (Funding, Open Interest, Mark/Index) so, dass:

- Spot, Margin und Futures **ohne stillen Informationsaustausch** nebeneinander laufen.
- Fehlende Funding-/OI-Daten **keinen Pipeline-Abbruch** erzwingen, wenn die Capability
  fehlt oder die Boerse nichts liefert.
- Der spaetere Handelskern anhand von **`pipeline_trade_mode`** zwischen
  `ok`, `analytics_only` und `do_not_trade` unterscheiden kann.

## Schichten

| Schicht                 | Inhalt                                     | Dienste                                                   |
| ----------------------- | ------------------------------------------ | --------------------------------------------------------- |
| Oeffentliche Marktdaten | Candles, Trades, Ticker-Bid/Ask, Orderbook | `market-stream`, TSDB                                     |
| Microstructure          | Spread, Tiefe, Impact, Imbalance           | `feature-engine` (`feat.bitget.public_microstructure.v1`) |
| Futures-Derivate        | Funding, OI, Mark/Index/Basis              | nur bei `market_family=futures` **und** Capability-Flags  |
| Margin-Kontext          | Kontext-Tag (keine Futures-Felder)         | `feat.bitget.margin_context.v1`                           |

Namensraeume und Bundle-Version: `shared_py.analysis.feature_namespaces` und
`FEATURE_NAMESPACE_BUNDLE_VERSION`.

## Capability-Gating

- **Katalogzeile** (`BitgetInstrumentCatalogEntry`): `supports_funding`,
  `supports_open_interest`, Eligibility (`analytics_eligible`, `live_execution_enabled`, …).
- **market-stream** (`TickerCollector`): REST-Polling und WS-Felder fuer Funding/OI werden
  nur genutzt, wenn Endpoint-Profil **und** Katalog das erlauben.
- **feature-engine**: Funding-/OI-Queries und Completeness-Checks greifen nur bei
  gesetzter Capability; sonst `not_applicable` und keine harten Fehler.

## Quality-Gates und `pipeline_trade_mode`

Implementierung: `shared_py.analysis.pipeline_gates`.

- Harte Issues (Identitaets-Mismatch, Cross-Family-Leak aus Ticker/DB-Pfad): tendenziell
  `do_not_trade`, Features werden dennoch geschrieben (Audit, Analytics-only-Kategorien).
- Tick-/Lot-Abgleich gegen Katalog-Metadaten: verschlechtert `feature_quality_status`,
  bleibt aber ohne DLQ.
- `pipeline_trade_mode`:
  - `ok`: Live-faehig (Qualitaet + Metadata + Live-Execution aktiv).
  - `analytics_only`: z. B. Live aus, abgeschwaechte Daten, oder nur Analyse freigeschaltet.
  - `do_not_trade`: harte Verletzungen / kein vertrauenswuerdiger Pfad.

Persistiert u. a. in `input_provenance_json.auxiliary_inputs` der Feature-Rows:
`pipeline_trade_mode`, `data_quality_issues`, `feature_namespaces`.

## Structure / Drawing (family-neutral)

- **structure-engine**: reine Candle-/Swing-/Kompressionslogik; optional
  `instrument_context` in `input_provenance`, wenn `candle_close` eine `instrument`-Identity
  traegt.
- **drawing-engine**: Kern aus Struktur + Orderbuch; `family_adapter` markiert Records nur
  mit Family-Tags / optionalen Overlay-Hinweisen — keine Futures-Logik im Kernalgorithmus.

## Tests

- `tests/unit/shared_py/analysis/test_analysis_pipeline.py` — Capability-Gating,
  Completeness, Pipeline-Modus, Leak-Gates.
- `tests/unit/feature_engine/test_microstructure_features.py` — Microstructure ohne OI-Capability.
- `tests/market-stream/test_ticker_capability_filter.py` — WS-Feld-Filter.

Siehe ergaenzend: `docs/features.md`.
