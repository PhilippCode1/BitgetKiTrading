# AI & Learning Engine (TimesFM & MLflow)

Die `learning-engine` und der `llm-orchestrator` repräsentieren das datengetriebene Gehirn des BitgetKiTrading-Systems. Sie kombinieren numerische Zero-Shot Forecasting Modelle (Google TimesFM) mit semantischer LLM-gestützter Auswertung und striktem ML-Lifecycle-Management via MLflow.

## 1. Google TimesFM Integration (Zero-Shot Forecasting)

Das System nutzt das Google TimesFM (Time Series Foundation Model) für die Vorhersage von Preis- und Volatilitätsentwicklungen. 

- **Inference Server (`services/inference-server/`)**: TimesFM wird in einem dedizierten Python-basierten gRPC-Server gekapselt. Dieser Server hält das Modell im VRAM (via GPU oder performanter CPU-Runtime) und verarbeitet Anfragen über `grpc_servicer.py`.
- **Numerical Patching (`tsfm_inference.py`)**: Die Inference-Client-Brücke sendet standardisierte numerische Zeitreihen-Patches an den Server und empfängt die Forecasts. Die Vorhersagen (z.B. Mean-Reversion Pressure, Directional Bias) fließen direkt als Features in das Data Lineage zurück.

## 2. LLM Orchestrator & Semantische Synthese

Anstatt LLMs für direkten Handel zu nutzen (was zu halluziniertem Risiko führen kann), werden LLMs als *semantische Synthese-Layer* verwendet, die hochkomplexe numerische Vektoren für den System-Operator in strukturierte Diagnosen übersetzen.

- **TSFM Semantics Agent (`tsfm_semantics.py`)**: Bewertet die rohen numerischen Outputs von TimesFM (z.B. `patch_incr_std`, Forecast Slope). Erzeugt deterministisch einen `directional_bias` (Long/Short/Neutral) und bewertet die Konfidenz (z.B. Mean-Reversion Score).
- **Prompt Governance**: Die LLM-Agenten unterliegen strengen Prompt-Regeln. Beispielsweise existieren strikte Direktiven wie `OPERATOR_MARKET_DATA_GAP_DIRECTIVE_DE`, die das Modell zwingen, fehlende Marktdaten als solche zu deklarieren und nicht zu extrapolieren.
- **Quant & Risk Governor Agents**: Andere Agenten wie `quant.py` und `risk_governor.py` analysieren das gesamte Signal und die Feature-Matrizen und bewerten Toxizität und Makro-Umfeld, bevor sie den Output an das Dashboard senden.

## 3. MLflow Lifecycle Management

Die kontinuierliche Evaluierung und Verfeinerung der Entscheidungslogik wird über MLflow getrackt (`mlflow_tracking/tracker.py`).

| Komponente | Beschreibung |
|---|---|
| **Parameter Tracking** | Aufzeichnung der verwendeten Konfigurationen (`learning_window_list`, `learning_promote_pf`, `learning_max_dd`) für jeden Evaluierungslauf. |
| **Metric Aggregation** | Flaches Mapping der aggregierten Metriken (Win-Rate, Drawdown, Profit-Factor) pro Analyse-Fenster und Veröffentlichung an den MLflow-Server. |
| **Artifact Logging** | Der komplette Report eines Runs (inklusive Signal-Matrizen und Backtest-Diagnostik) wird als JSON-Artefakt in MLflow hochgeladen. |

## 4. Data Lineage & Cross-Validation

- **Cross Validation Runner (`cv_runner.py`)**: Validiert Handelsstrategien deterministisch über historische Splits, um Overfitting zu verhindern. Verhindert explizit Data-Leakage (`check_leakage.py`).
- **Data Lineage**: Jedes Modell-Feature besitzt eine strikte Kette der Nachverfolgung (Lineage). So ist jederzeit nachvollziehbar, auf welchen Rohdaten (und in welchem Regime) eine Vorhersage basierte. Dies garantiert Reproduzierbarkeit im Paper/Live-Trading.
