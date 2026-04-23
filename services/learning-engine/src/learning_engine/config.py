from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, StrategyRegistryStatus

_TAKE_TRADE_CALIBRATION_METHODS = ("sigmoid", "isotonic")


class LearningEngineSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("database_url", "redis_url")
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields
        + ("database_url", "redis_url")
    )

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    learning_engine_port: int = Field(default=8090, alias="LEARNING_ENGINE_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    learn_consumer_group: str = Field(default="learning-engine", alias="LEARN_CONSUMER_GROUP")
    learn_consumer_name: str = Field(default="le-1", alias="LEARN_CONSUMER_NAME")
    learn_stream_trade_closed: str = Field(default="events:trade_closed", alias="LEARN_STREAM_TRADE_CLOSED")
    learn_stream_trade_opened: str = Field(default="events:trade_opened", alias="LEARN_STREAM_TRADE_OPENED")
    learn_stream_trade_updated: str = Field(default="events:trade_updated", alias="LEARN_STREAM_TRADE_UPDATED")
    learn_stream_signal_created: str = Field(default="events:signal_created", alias="LEARN_STREAM_SIGNAL_CREATED")
    learn_stream_news_scored: str = Field(default="events:news_scored", alias="LEARN_STREAM_NEWS_SCORED")
    learn_stream_structure_updated: str = Field(
        default="events:structure_updated", alias="LEARN_STREAM_STRUCTURE_UPDATED"
    )
    learn_stream_drawing_updated: str = Field(
        default="events:drawing_updated", alias="LEARN_STREAM_DRAWING_UPDATED"
    )
    learn_stream_risk_alert: str = Field(default="events:risk_alert", alias="LEARN_STREAM_RISK_ALERT")
    learn_consume_optional_streams: bool = Field(default=True, alias="LEARN_CONSUME_OPTIONAL_STREAMS")
    learn_stream_system_alert: str = Field(default="events:system_alert", alias="LEARN_STREAM_SYSTEM_ALERT")

    self_healing_enabled: bool = Field(default=False, alias="SELF_HEALING_ENABLED")
    self_healing_trigger_svc_critical: bool = Field(
        default=False,
        alias="SELF_HEALING_TRIGGER_SVC_CRITICAL",
        description="Zusaetzlich: svc:* critical system_alerts (ohne CRITICAL_RUNTIME_EXCEPTION).",
    )
    llm_orchestrator_base_url: str = Field(
        default="http://127.0.0.1:8070",
        alias="LLM_ORCHESTRATOR_BASE_URL",
        description="Structured-LLM fuer Self-Healing-Diagnose.",
    )
    audit_ledger_base_url: str = Field(
        default="",
        alias="AUDIT_LEDGER_BASE_URL",
        description="Optional: Audit-Ledger verify-chain als Kontext (keine Stacktraces).",
    )
    self_healing_sandbox_timeout_sec: float = Field(
        default=420.0,
        ge=30.0,
        le=3600.0,
        alias="SELF_HEALING_SANDBOX_TIMEOUT_SEC",
    )
    self_healing_apply_enabled: bool = Field(
        default=False,
        alias="SELF_HEALING_APPLY_ENABLED",
        description="Nur nach expliziter Freigabe: Patch anwenden (gefaehrlich).",
    )
    self_healing_apply_path_prefixes: str = Field(
        default="services/,shared/python/",
        alias="SELF_HEALING_APPLY_PATH_PREFIXES",
        description="CSV erlaubter relativer Pfad-Praefixe fuer APPLY.",
    )
    self_healing_docker_restart: str = Field(
        default="",
        alias="SELF_HEALING_DOCKER_RESTART",
        description="Optional: Compose-Service-Name fuer docker compose restart (leer=aus).",
    )

    news_context_lookback_ms: int = Field(default=3_600_000, alias="NEWS_CONTEXT_LOOKBACK_MS")
    news_context_lookahead_ms: int = Field(default=900_000, alias="NEWS_CONTEXT_LOOKAHEAD_MS")
    learn_stop_min_atr_mult: str = Field(default="0.6", alias="LEARN_STOP_MIN_ATR_MULT")
    learn_false_breakout_window_ms: int = Field(default=600_000, alias="LEARN_FALSE_BREAKOUT_WINDOW_MS")
    learn_stale_signal_ms: int = Field(default=3_600_000, alias="LEARN_STALE_SIGNAL_MS")
    learn_max_feature_age_ms: int = Field(default=3_600_000, alias="LEARN_MAX_FEATURE_AGE_MS")
    learn_multi_tf_threshold: int = Field(default=40, alias="LEARN_MULTI_TF_THRESHOLD")
    paper_mmr_base: str = Field(default="0.005", alias="PAPER_MMR_BASE")
    paper_liq_fee_buffer_usdt: str = Field(default="5", alias="PAPER_LIQ_FEE_BUFFER_USDT")
    eventbus_block_ms: int = Field(default=2000, alias="EVENTBUS_DEFAULT_BLOCK_MS")
    eventbus_count: int = Field(default=20, alias="EVENTBUS_DEFAULT_COUNT")

    strategy_registry_enabled: bool = Field(default=True, alias="STRATEGY_REGISTRY_ENABLED")
    strategy_registry_default_status: StrategyRegistryStatus = Field(
        default="shadow",
        alias="STRATEGY_REGISTRY_DEFAULT_STATUS",
    )
    strategy_registry_event_stream: str = Field(
        default="events:strategy_registry_updated", alias="STRATEGY_REGISTRY_EVENT_STREAM"
    )

    @field_validator("strategy_registry_default_status")
    @classmethod
    def _reg_def_status(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ("promoted", "candidate", "shadow", "retired"):
            raise ValueError("STRATEGY_REGISTRY_DEFAULT_STATUS ungueltig")
        return s

    @field_validator("strategy_registry_event_stream")
    @classmethod
    def _reg_stream(cls, v: str) -> str:
        allowed = "events:strategy_registry_updated"
        x = v.strip()
        if x != allowed:
            raise ValueError(f"STRATEGY_REGISTRY_EVENT_STREAM muss {allowed!r} sein (Redis-Whitelist)")
        return x

    learning_window_list: str = Field(default="1d,7d,30d", alias="LEARNING_WINDOW_LIST")
    learning_promote_pf: float = Field(default=1.4, alias="LEARNING_PROMOTE_PF")
    learning_retire_pf: float = Field(default=0.9, alias="LEARNING_RETIRE_PF")
    learning_max_dd: float = Field(default=0.15, alias="LEARNING_MAX_DD")
    learning_enable_adwin: bool = Field(default=True, alias="LEARNING_ENABLE_ADWIN")
    learning_adwin_metric: str = Field(default="pnl_net_usdt", alias="LEARNING_ADWIN_METRIC")
    learning_enable_mlflow: bool = Field(default=False, alias="LEARNING_ENABLE_MLFLOW")
    mlflow_tracking_uri: str = Field(default="", alias="MLFLOW_TRACKING_URI")

    adversarial_engine_base_url: str = Field(
        default="http://adversarial-engine:8145",
        alias="ADVERSARIAL_ENGINE_BASE_URL",
        description="HTTP-Basis fuer AMS toxische Batches (Proxy unter /learning/adversarial/toxic-batch).",
    )
    model_promotion_require_adversarial_stress: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_REQUIRE_ADVERSARIAL_STRESS",
        description="Champion-Promotion: 1000er AMS-Stresstest + Resilience >= Schwelle.",
    )
    adversarial_stress_attack_count: int = Field(
        default=1000,
        ge=100,
        le=50_000,
        alias="ADVERSARIAL_STRESS_ATTACK_COUNT",
    )
    adversarial_stress_trap_toxicity_threshold: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        alias="ADVERSARIAL_STRESS_TRAP_TOXICITY_THRESHOLD",
    )
    model_promotion_min_resilience_score_0_100: float = Field(
        default=90.0,
        ge=0.0,
        le=100.0,
        alias="MODEL_PROMOTION_MIN_RESILIENCE_SCORE_0_100",
    )
    risk_toxicity_classifier_model_path: str = Field(
        default="",
        alias="RISK_TOXICITY_CLASSIFIER_MODEL_PATH",
        description="joblib-Pfad (RandomForest) fuer AMS-Stress + Risk-Governor-Export.",
    )

    @field_validator("learning_adwin_metric")
    @classmethod
    def _adwin_m(cls, v: str) -> str:
        x = v.strip().lower()
        if x not in ("pnl_net_usdt", "win_rate"):
            raise ValueError("LEARNING_ADWIN_METRIC muss pnl_net_usdt oder win_rate sein")
        return x

    @field_validator(
        "learn_false_breakout_window_ms",
        "learn_stale_signal_ms",
        "learn_max_feature_age_ms",
        "news_context_lookback_ms",
        "news_context_lookahead_ms",
    )
    @classmethod
    def _positive_windows(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("LEARN_*/NEWS_* Zeitfenster muessen > 0 sein")
        return v

    backtest_artifacts_dir: str = Field(default="artifacts/backtests", alias="BACKTEST_ARTIFACTS_DIR")
    research_benchmark_artifacts_dir: str = Field(
        default="artifacts/research",
        alias="RESEARCH_BENCHMARK_ARTIFACTS_DIR",
        description="CLI/Operator: JSON+Markdown Evidence-Reports (keine Secrets).",
    )
    research_benchmark_default_eval_limit: int = Field(
        default=2000,
        alias="RESEARCH_BENCHMARK_DEFAULT_EVAL_LIMIT",
    )
    research_benchmark_default_e2e_limit: int = Field(
        default=500,
        alias="RESEARCH_BENCHMARK_DEFAULT_E2E_LIMIT",
    )
    research_benchmark_read_secret: str | None = Field(
        default=None,
        alias="RESEARCH_BENCHMARK_READ_SECRET",
        description="Wenn gesetzt: GET /learning/research/benchmark-evidence erfordert X-Research-Benchmark-Secret.",
    )
    model_artifacts_dir: str = Field(default="artifacts/models", alias="MODEL_ARTIFACTS_DIR")
    take_trade_model_artifacts_dir: str | None = Field(
        default=None,
        alias="TAKE_TRADE_MODEL_ARTIFACTS_DIR",
    )
    expected_bps_model_artifacts_dir: str | None = Field(
        default=None,
        alias="EXPECTED_BPS_MODEL_ARTIFACTS_DIR",
    )
    regime_classifier_model_artifacts_dir: str | None = Field(
        default=None,
        alias="REGIME_CLASSIFIER_MODEL_ARTIFACTS_DIR",
    )
    take_trade_model_min_rows: int = Field(default=80, alias="TAKE_TRADE_MODEL_MIN_ROWS")
    expected_bps_model_min_rows: int = Field(
        default=96,
        alias="EXPECTED_BPS_MODEL_MIN_ROWS",
    )
    take_trade_model_min_positive_rows: int = Field(
        default=12,
        alias="TAKE_TRADE_MODEL_MIN_POSITIVE_ROWS",
    )
    take_trade_model_calibration_method: str = Field(
        default="sigmoid",
        alias="TAKE_TRADE_MODEL_CALIBRATION_METHOD",
    )
    backtest_default_cv: str = Field(default="walk_forward", alias="BACKTEST_DEFAULT_CV")
    backtest_purged_embargo_pct: float = Field(default=0.05, alias="BACKTEST_PURGED_EMBARGO_PCT")
    backtest_kfolds: int = Field(default=5, alias="BACKTEST_KFOLDS")
    train_cv_kfolds: int = Field(default=5, alias="TRAIN_CV_KFOLDS")
    train_cv_embargo_pct: float = Field(default=0.05, alias="TRAIN_CV_EMBARGO_PCT")
    train_random_state: int = Field(default=42, alias="TRAIN_RANDOM_STATE")
    specialist_family_min_rows: int = Field(
        default=40,
        alias="SPECIALIST_FAMILY_MIN_ROWS",
        description="Mindestzeilen pro market_family fuer eigenstaendige Familien-Spezialisten (sonst Pool/Degrade).",
    )
    specialist_cluster_min_rows: int = Field(
        default=80,
        alias="SPECIALIST_CLUSTER_MIN_ROWS",
        description="Mindestzeilen pro Cluster (market_family::market_regime) fuer Cluster-Experten.",
    )
    specialist_regime_min_rows: int = Field(
        default=60,
        alias="SPECIALIST_REGIME_MIN_ROWS",
        description="Mindestzeilen pro market_regime-Segment fuer Regime-Spezialisten.",
    )
    specialist_playbook_min_rows: int = Field(
        default=50,
        alias="SPECIALIST_PLAYBOOK_MIN_ROWS",
        description="Mindestzeilen mit erkennbarer playbook_id im Signal-Snapshot fuer Playbook-Experten.",
    )
    specialist_symbol_min_rows: int = Field(
        default=500,
        alias="SPECIALIST_SYMBOL_MIN_ROWS",
        description="Mindest-Trainingszeilen pro Symbol fuer Symbol-Scoped Champion/Promotion.",
    )
    regime_classifier_min_rows: int = Field(default=120, alias="REGIME_CLASSIFIER_MIN_ROWS")
    regime_classifier_min_per_class: int = Field(default=8, alias="REGIME_CLASSIFIER_MIN_PER_CLASS")
    replay_speed_factor: float = Field(default=60.0, alias="REPLAY_SPEED_FACTOR")
    model_calibration_required: bool = Field(default=False, alias="MODEL_CALIBRATION_REQUIRED")
    model_champion_name: str = Field(default="take_trade_prob", alias="MODEL_CHAMPION_NAME")

    model_promotion_gates_enabled: bool = Field(default=False, alias="MODEL_PROMOTION_GATES_ENABLED")
    model_promotion_min_walk_forward_mean_roc_auc: float = Field(
        default=0.52,
        alias="MODEL_PROMOTION_MIN_WALK_FORWARD_MEAN_ROC_AUC",
    )
    model_promotion_min_purged_kfold_mean_roc_auc: float = Field(
        default=0.52,
        alias="MODEL_PROMOTION_MIN_PURGED_KFOLD_MEAN_ROC_AUC",
    )
    model_promotion_min_test_roc_auc_take_trade: float = Field(
        default=0.50,
        alias="MODEL_PROMOTION_MIN_TEST_ROC_AUC_TAKE_TRADE",
    )
    model_promotion_max_test_brier_take_trade: float = Field(
        default=0.40,
        alias="MODEL_PROMOTION_MAX_TEST_BRIER_TAKE_TRADE",
    )
    model_promotion_min_walk_forward_mean_accuracy_regime: float = Field(
        default=0.35,
        alias="MODEL_PROMOTION_MIN_WALK_FORWARD_MEAN_ACCURACY_REGIME",
    )
    model_promotion_min_purged_kfold_mean_accuracy_regime: float = Field(
        default=0.35,
        alias="MODEL_PROMOTION_MIN_PURGED_KFOLD_MEAN_ACCURACY_REGIME",
    )
    model_promotion_require_shadow_evidence: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE",
    )
    model_promotion_manual_override_enabled: bool = Field(
        default=True,
        alias="MODEL_PROMOTION_MANUAL_OVERRIDE_ENABLED",
    )
    model_registry_auto_rollback_on_drift_hard_block: bool = Field(
        default=False,
        alias="MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK",
    )
    model_registry_auto_rollback_model_name: str = Field(
        default="take_trade_prob",
        alias="MODEL_REGISTRY_AUTO_ROLLBACK_MODEL_NAME",
    )
    model_registry_mutation_secret: str | None = Field(
        default=None,
        alias="MODEL_REGISTRY_MUTATION_SECRET",
        description="Wenn gesetzt: POST/DELETE Registry-V2 erfordert Header X-Model-Registry-Mutation-Secret.",
    )

    model_promotion_fail_on_cv_symbol_leakage_take_trade: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_FAIL_ON_CV_SYMBOL_LEAKAGE_TAKE_TRADE",
    )
    model_promotion_max_cv_symbol_overlap_folds_take_trade: int = Field(
        default=0,
        alias="MODEL_PROMOTION_MAX_CV_SYMBOL_OVERLAP_FOLDS_TAKE_TRADE",
        description="Zulaessige Folds mit strict_symbol_overlap in Walk-Forward oder Purged-CV (0 = keiner).",
    )
    model_promotion_require_trade_relevance_gates_take_trade: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_REQUIRE_TRADE_RELEVANCE_GATES_TAKE_TRADE",
    )
    model_promotion_trade_relevance_max_high_conf_fp_rate: float = Field(
        default=0.42,
        alias="MODEL_PROMOTION_TRADE_RELEVANCE_MAX_HIGH_CONF_FP_RATE",
        description="Obere Grenze fuer high_confidence_false_positive_rate aus trade_relevance_summary.",
    )
    model_promotion_require_governance_artifacts: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_REQUIRE_GOVERNANCE_ARTIFACTS",
        description="Wenn true: data_version_hash, dataset_hash, feature_contract.schema_hash, training_manifest-Ref, Kalibrierungsnachweis.",
    )
    model_promotion_require_inference_behavior_metadata: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_REQUIRE_INFERENCE_BEHAVIOR_METADATA",
        description="Optional: inference_fallback_policy + inference_abstention_policy in metadata_json.",
    )
    model_promotion_apply_online_drift_gate: bool = Field(
        default=False,
        alias="MODEL_PROMOTION_APPLY_ONLINE_DRIFT_GATE",
        description="Bei take_trade_prob + globalem Scope: Promotion blocken wenn Online-Drift in blockierten Stufen.",
    )
    model_promotion_online_drift_blocked_tiers_csv: str = Field(
        default="shadow_only,hard_block",
        alias="MODEL_PROMOTION_ONLINE_DRIFT_BLOCKED_TIERS",
        description="Komma-getrennt: warn, shadow_only, hard_block — Promotion stoppt wenn effective_action enthalten.",
    )
    learning_context_ingest_secret: str | None = Field(
        default=None,
        alias="LEARNING_CONTEXT_INGEST_SECRET",
        description="Wenn gesetzt: POST /learning/governance/context-signals erfordert X-Learning-Context-Ingest-Secret.",
    )

    online_drift_lookback_minutes: int = Field(default=60, alias="ONLINE_DRIFT_LOOKBACK_MINUTES")
    online_drift_max_signals_sample: int = Field(default=400, alias="ONLINE_DRIFT_MAX_SIGNALS_SAMPLE")
    online_drift_min_samples: int = Field(default=25, alias="ONLINE_DRIFT_MIN_SAMPLES")
    online_drift_evaluate_on_analytics_run: bool = Field(
        default=True,
        alias="ONLINE_DRIFT_EVALUATE_ON_ANALYTICS_RUN",
    )
    online_drift_feature_stale_age_ms: int = Field(
        default=300_000,
        alias="ONLINE_DRIFT_FEATURE_STALE_AGE_MS",
    )
    online_drift_ood_mean_warn: float = Field(default=0.28, alias="ONLINE_DRIFT_OOD_MEAN_WARN")
    online_drift_ood_mean_shadow: float = Field(default=0.40, alias="ONLINE_DRIFT_OOD_MEAN_SHADOW")
    online_drift_ood_mean_block: float = Field(default=0.52, alias="ONLINE_DRIFT_OOD_MEAN_BLOCK")
    online_drift_regime_tv_warn: float = Field(default=0.22, alias="ONLINE_DRIFT_REGIME_TV_WARN")
    online_drift_regime_tv_shadow: float = Field(default=0.38, alias="ONLINE_DRIFT_REGIME_TV_SHADOW")
    online_drift_regime_tv_block: float = Field(default=0.52, alias="ONLINE_DRIFT_REGIME_TV_BLOCK")
    online_drift_stale_frac_warn: float = Field(default=0.20, alias="ONLINE_DRIFT_STALE_FRAC_WARN")
    online_drift_stale_frac_shadow: float = Field(default=0.40, alias="ONLINE_DRIFT_STALE_FRAC_SHADOW")
    online_drift_stale_frac_block: float = Field(default=0.60, alias="ONLINE_DRIFT_STALE_FRAC_BLOCK")
    online_drift_prob_std_warn: float = Field(default=0.14, alias="ONLINE_DRIFT_PROB_STD_WARN")
    online_drift_prob_std_shadow: float = Field(default=0.22, alias="ONLINE_DRIFT_PROB_STD_SHADOW")
    online_drift_prob_std_block: float = Field(default=0.32, alias="ONLINE_DRIFT_PROB_STD_BLOCK")
    online_drift_ood_alert_frac_warn: float = Field(
        default=0.12,
        alias="ONLINE_DRIFT_OOD_ALERT_FRAC_WARN",
    )
    online_drift_ood_alert_frac_shadow: float = Field(
        default=0.28,
        alias="ONLINE_DRIFT_OOD_ALERT_FRAC_SHADOW",
    )
    online_drift_ood_alert_frac_block: float = Field(
        default=0.45,
        alias="ONLINE_DRIFT_OOD_ALERT_FRAC_BLOCK",
    )
    online_drift_missing_prob_frac_warn: float = Field(
        default=0.06,
        alias="ONLINE_DRIFT_MISSING_PROB_FRAC_WARN",
    )
    online_drift_missing_prob_frac_shadow: float = Field(
        default=0.14,
        alias="ONLINE_DRIFT_MISSING_PROB_FRAC_SHADOW",
    )
    online_drift_missing_prob_frac_block: float = Field(
        default=0.28,
        alias="ONLINE_DRIFT_MISSING_PROB_FRAC_BLOCK",
    )
    online_drift_shadow_prob_mae_warn: float = Field(
        default=0.12,
        alias="ONLINE_DRIFT_SHADOW_PROB_MAE_WARN",
    )
    online_drift_shadow_prob_mae_shadow: float = Field(
        default=0.22,
        alias="ONLINE_DRIFT_SHADOW_PROB_MAE_SHADOW",
    )
    online_drift_shadow_prob_mae_block: float = Field(
        default=0.35,
        alias="ONLINE_DRIFT_SHADOW_PROB_MAE_BLOCK",
    )

    @field_validator("backtest_default_cv")
    @classmethod
    def _bt_cv(cls, v: str) -> str:
        x = v.strip().lower()
        if x not in ("walk_forward", "purged_kfold_embargo"):
            raise ValueError("BACKTEST_DEFAULT_CV ungueltig")
        return x

    @field_validator("backtest_kfolds", "train_cv_kfolds")
    @classmethod
    def _bt_k(cls, v: int) -> int:
        if v < 2 or v > 20:
            raise ValueError("KFolds muss 2..20 sein (BACKTEST_KFOLDS / TRAIN_CV_KFOLDS)")
        return v

    @field_validator("train_cv_embargo_pct", "backtest_purged_embargo_pct")
    @classmethod
    def _train_embargo(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("Embargo-Anteil muss 0..1 sein")
        return v

    @field_validator("research_benchmark_default_eval_limit", "research_benchmark_default_e2e_limit")
    @classmethod
    def _research_limits(cls, v: int) -> int:
        if v < 1 or v > 50_000:
            raise ValueError("RESEARCH_BENCHMARK_*_LIMIT muss 1..50000 sein")
        return v

    @model_validator(mode="before")
    @classmethod
    def _empty_artifact_env_to_none(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        for key in (
            "TAKE_TRADE_MODEL_ARTIFACTS_DIR",
            "EXPECTED_BPS_MODEL_ARTIFACTS_DIR",
            "REGIME_CLASSIFIER_MODEL_ARTIFACTS_DIR",
            "RESEARCH_BENCHMARK_READ_SECRET",
            "LEARNING_CONTEXT_INGEST_SECRET",
        ):
            if data.get(key) == "":
                data[key] = None
        return data

    @model_validator(mode="after")
    def _default_model_artifact_subdirs(self) -> Self:
        root = Path(self.model_artifacts_dir)
        if self.take_trade_model_artifacts_dir is None:
            object.__setattr__(self, "take_trade_model_artifacts_dir", str(root / "take_trade_prob"))
        if self.expected_bps_model_artifacts_dir is None:
            object.__setattr__(self, "expected_bps_model_artifacts_dir", str(root / "expected_bps"))
        if self.regime_classifier_model_artifacts_dir is None:
            object.__setattr__(self, "regime_classifier_model_artifacts_dir", str(root / "regime_classifier"))
        return self

    @field_validator(
        "take_trade_model_min_rows",
        "expected_bps_model_min_rows",
        "take_trade_model_min_positive_rows",
        "specialist_family_min_rows",
        "specialist_cluster_min_rows",
        "specialist_regime_min_rows",
        "specialist_playbook_min_rows",
        "specialist_symbol_min_rows",
        "regime_classifier_min_rows",
        "regime_classifier_min_per_class",
    )
    @classmethod
    def _positive_meta_model_counts(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Modell-Trainings-Counts muessen > 0 sein")
        return v

    @field_validator(
        "online_drift_lookback_minutes",
        "online_drift_max_signals_sample",
        "online_drift_min_samples",
        "online_drift_feature_stale_age_ms",
    )
    @classmethod
    def _positive_online_drift(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ONLINE_DRIFT_* Counts und Fenster muessen > 0 sein")
        return v

    @field_validator(
        "online_drift_ood_mean_warn",
        "online_drift_ood_mean_shadow",
        "online_drift_ood_mean_block",
        "online_drift_regime_tv_warn",
        "online_drift_regime_tv_shadow",
        "online_drift_regime_tv_block",
        "online_drift_stale_frac_warn",
        "online_drift_stale_frac_shadow",
        "online_drift_stale_frac_block",
        "online_drift_prob_std_warn",
        "online_drift_prob_std_shadow",
        "online_drift_prob_std_block",
        "online_drift_ood_alert_frac_warn",
        "online_drift_ood_alert_frac_shadow",
        "online_drift_ood_alert_frac_block",
        "online_drift_missing_prob_frac_warn",
        "online_drift_missing_prob_frac_shadow",
        "online_drift_missing_prob_frac_block",
        "online_drift_shadow_prob_mae_warn",
        "online_drift_shadow_prob_mae_shadow",
        "online_drift_shadow_prob_mae_block",
    )
    @classmethod
    def _online_drift_threshold_order(cls, v: float) -> float:
        if v < 0 or v > 1.5:
            raise ValueError("Online-Drift-Schwellen muessen sinnvoll 0..1.5 bleiben")
        return v

    @field_validator(
        "model_promotion_min_walk_forward_mean_roc_auc",
        "model_promotion_min_purged_kfold_mean_roc_auc",
        "model_promotion_min_test_roc_auc_take_trade",
        "model_promotion_max_test_brier_take_trade",
        "model_promotion_min_walk_forward_mean_accuracy_regime",
        "model_promotion_min_purged_kfold_mean_accuracy_regime",
        "model_promotion_trade_relevance_max_high_conf_fp_rate",
    )
    @classmethod
    def _promotion_thresholds_sane(cls, v: float) -> float:
        if v < 0 or v > 1.0:
            raise ValueError("Promotions-Schwellen fuer AUC/Accuracy/Brier muessen 0..1 sein")
        return v

    @field_validator("model_promotion_max_cv_symbol_overlap_folds_take_trade")
    @classmethod
    def _cv_symbol_overlap_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("MODEL_PROMOTION_MAX_CV_SYMBOL_OVERLAP_FOLDS_TAKE_TRADE muss >= 0 sein")
        return v

    @field_validator("take_trade_model_calibration_method")
    @classmethod
    def _meta_model_calibration_method(cls, v: str) -> str:
        x = v.strip().lower()
        if x not in _TAKE_TRADE_CALIBRATION_METHODS:
            raise ValueError(
                "TAKE_TRADE_MODEL_CALIBRATION_METHOD muss "
                + " oder ".join(_TAKE_TRADE_CALIBRATION_METHODS)
                + " sein"
            )
        return x
