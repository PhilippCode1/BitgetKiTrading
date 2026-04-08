"""
Spezialisten-Pfade: Mindestdaten pro Marktfamilie, Cluster (Familie+Regime), Regime, Playbook, Symbol.

Vollständige separierte Modell-Artefakte pro Familie/Router/Exit sind Zielbild; diese Audit-Funktion
verhindert, dass Operatoren „leere“ Spezialisten-Runs als produktionsreif interpretieren.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg

from learning_engine.config import LearningEngineSettings
from learning_engine.curriculum.expert_curriculum import cluster_expert_key
from learning_engine.storage import repo_model_runs
from learning_engine.training.constants import TRAINING_PIPELINE_VERSION
from shared_py.training_dataset_builder import TakeTradeDatasetBuildConfig, build_take_trade_training_dataset


def _playbook_id_from_row(row: dict[str, Any]) -> str | None:
    raw = row.get("signal_snapshot_json")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if not isinstance(raw, dict):
        return None
    pid = raw.get("playbook_id")
    if isinstance(pid, str) and pid.strip():
        return pid.strip().lower()
    spec = raw.get("specialists")
    if isinstance(spec, dict):
        pb = spec.get("playbook_specialist")
        if isinstance(pb, dict):
            for k in ("playbook_id", "selected_playbook_id", "specialist_id"):
                v = pb.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip().lower()
    return None


SPECIALIST_ROLE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "role_id": "base_take_trade_prob",
        "description_de": "Kalibriertes Take-Trade-Metamodell (Pool)",
        "train_job": "take-trade",
    },
    {
        "role_id": "expected_bps_heads",
        "description_de": "Return/MAE/MFE BPS-Regressionen",
        "train_job": "expected-bps",
    },
    {
        "role_id": "regime_classifier",
        "description_de": "Marktregime Multiklassifikation",
        "train_job": "regime",
    },
    {
        "role_id": "family_conditional_overlay",
        "description_de": "Optional: familienspezifische Feinkalibrierung — nur bei Mindestzeilen",
        "train_job": None,
        "min_rows_per_family": "specialist_family_min_rows",
    },
    {
        "role_id": "cluster_expert",
        "description_de": "Generischer Spezialist market_family::market_regime — bevorzugt bei duennen Symbol-Daten",
        "train_job": None,
        "min_rows_per_cluster": "specialist_cluster_min_rows",
    },
    {
        "role_id": "regime_expert",
        "description_de": "Regime-Segment — eigener Champion-Scope market_regime",
        "train_job": None,
        "min_rows_per_regime": "specialist_regime_min_rows",
    },
    {
        "role_id": "playbook_expert",
        "description_de": "Playbook-Segment aus signal_snapshot_json — Scope playbook",
        "train_job": None,
        "min_rows_per_playbook": "specialist_playbook_min_rows",
    },
    {
        "role_id": "symbol_expert",
        "description_de": "Symbol-Spezialist nur bei hoher Zeilendichte (Nachweis)",
        "train_job": None,
        "min_rows_per_symbol": "specialist_symbol_min_rows",
    },
    {
        "role_id": "router_exit_stop_specialists",
        "description_de": "Router/Exit/Stop-Qualität: dedizierte Trainingspfade erfordern E2E-Labels + ausreichend Volumen",
        "train_job": None,
        "status_default": "data_pipeline_pending",
    },
)


def audit_specialist_training_readiness(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    symbol: str | None = None,
) -> dict[str, Any]:
    rows = repo_model_runs.fetch_take_trade_training_rows(conn, symbol=symbol)
    cfg = TakeTradeDatasetBuildConfig(max_feature_age_ms=settings.learn_max_feature_age_ms)
    examples, report = build_take_trade_training_dataset(rows, cfg)
    by_family: dict[str, int] = {}
    by_regime: dict[str, int] = {}
    by_cluster: dict[str, int] = {}
    by_symbol: dict[str, int] = {}
    for ex in examples:
        fam = str(ex.get("market_family") or "unknown")
        by_family[fam] = by_family.get(fam, 0) + 1
        reg = str(ex.get("market_regime") or "unknown")
        by_regime[reg] = by_regime.get(reg, 0) + 1
        ck = cluster_expert_key(market_family=fam, market_regime=reg)
        by_cluster[ck] = by_cluster.get(ck, 0) + 1
        sym = str(ex.get("symbol") or "unknown").strip().upper() or "UNKNOWN"
        by_symbol[sym] = by_symbol.get(sym, 0) + 1

    by_playbook: dict[str, int] = {}
    for row in rows:
        pb = _playbook_id_from_row(row)
        if pb:
            by_playbook[pb] = by_playbook.get(pb, 0) + 1

    min_f = settings.specialist_family_min_rows
    min_reg = settings.specialist_regime_min_rows
    min_cl = settings.specialist_cluster_min_rows
    min_pb = settings.specialist_playbook_min_rows
    min_sym = settings.specialist_symbol_min_rows

    family_audit = [
        {
            "market_family": fam,
            "n_after_gates": n,
            "standalone_family_specialist_recommended": n >= min_f,
            "degrade_to_pooled_model": n < min_f,
        }
        for fam, n in sorted(by_family.items(), key=lambda x: (-x[1], x[0]))
    ]
    thin = [x for x in family_audit if x["degrade_to_pooled_model"] and x["market_family"] != "unknown"]

    regime_audit = [
        {
            "market_regime": rg,
            "n_after_gates": n,
            "regime_expert_viable": n >= min_reg,
        }
        for rg, n in sorted(by_regime.items(), key=lambda x: (-x[1], x[0]))
    ]
    regimes_thin = [x for x in regime_audit if not x["regime_expert_viable"] and x["market_regime"] != "unknown"]

    cluster_audit = [
        {
            "cluster_key": ck,
            "n_after_gates": n,
            "cluster_expert_recommended": n >= min_cl,
            "degrade_to_pooled_model": n < min_cl,
        }
        for ck, n in sorted(by_cluster.items(), key=lambda x: (-x[1], x[0]))
    ]
    clusters_thin = [x for x in cluster_audit if x["degrade_to_pooled_model"]]

    playbook_audit = [
        {
            "playbook_id": pb,
            "n_rows_with_playbook_tag": n,
            "playbook_expert_viable": n >= min_pb,
        }
        for pb, n in sorted(by_playbook.items(), key=lambda x: (-x[1], x[0]))
    ]
    playbooks_thin = [x for x in playbook_audit if not x["playbook_expert_viable"]]

    symbol_audit = [
        {
            "symbol": sy,
            "n_after_gates": n,
            "symbol_specialist_viable": n >= min_sym,
            "degrade_to_cluster_expert": n < min_sym,
        }
        for sy, n in sorted(by_symbol.items(), key=lambda x: (-x[1], x[0]))
    ]
    symbols_thin = [x for x in symbol_audit if x["degrade_to_cluster_expert"] and x["symbol"] != "UNKNOWN"]

    return {
        "schema_version": "specialist-readiness-v2",
        "training_pipeline_version": TRAINING_PIPELINE_VERSION,
        "symbol_filter": symbol.upper() if symbol else None,
        "raw_row_count": len(rows),
        "examples_after_gates": len(examples),
        "dataset_build": {
            "config_fingerprint": report.config_fingerprint,
            "dropped": report.dropped,
        },
        "family_audit": family_audit,
        "families_below_min_rows": thin,
        "regime_audit": regime_audit,
        "regimes_below_min_rows": regimes_thin,
        "cluster_audit": cluster_audit,
        "clusters_below_min_rows": clusters_thin,
        "playbook_audit": playbook_audit,
        "playbooks_below_min_rows": playbooks_thin,
        "symbol_audit": symbol_audit,
        "symbols_below_min_rows": symbols_thin,
        "role_definitions": list(SPECIALIST_ROLE_DEFINITIONS),
        "policy": {
            "specialist_family_min_rows": min_f,
            "specialist_cluster_min_rows": min_cl,
            "specialist_regime_min_rows": min_reg,
            "specialist_playbook_min_rows": min_pb,
            "specialist_symbol_min_rows": min_sym,
            "note_de": (
                "Familien/Cluster unter Mindestzeilen nicht als eigenständige Produktions-Spezialisten "
                "promoten; Pool-Modell + Monitoring. Symbol-Spezialisten nur ab SPECIALIST_SYMBOL_MIN_ROWS."
            ),
        },
    }
