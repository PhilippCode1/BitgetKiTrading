"""
Autonomer Survival-Mode: Market-Regime-Disruption (TimesFM-Residual, AMS-Toxizitaet, Drift-Z).

- Kernlogik: Rust `survival_kernel` (FFI, optional) — identische Python-Fallback-Schleife.
- Zustand: Redis `ops:survival_kernel:v1` oder reines Env `BITGET_SURVIVAL_MODE=1` fuer Tests.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

from shared_py.eventbus.envelope import STREAM_SYSTEM_ALERT, EventEnvelope

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger("shared_py.resilience.survival_kernel")

SYSTEM_ENTER_SURVIVAL_MODE = "SYSTEM_ENTER_SURVIVAL_MODE"
SYSTEM_EXIT_SURVIVAL_MODE = "SYSTEM_EXIT_SURVIVAL_MODE"
SURVIVAL_REDIS_KEY = "ops:survival_kernel:v1"
SURVIVAL_ENV_FLAG = "BITGET_SURVIVAL_MODE"
SURVIVAL_LIB_ENV = "SURVIVAL_KERNEL_LIB_PATH"


@dataclass(frozen=True)
class SurvivalMetrics:
    """Eingaben aus Online-Drift, TimesFM (inference-server) und AMS (adversarial-engine)."""

    drift_z: float
    tsfm_residual_z: float
    ams_toxicity_0_1: float


@dataclass(frozen=True)
class SurvivalKernelParams:
    enter_threshold: float = 6.0
    exit_threshold: float = 3.5
    exit_hysteresis_ticks: int = 5


@dataclass
class SurvivalTickResult:
    in_survival: bool
    consec_low_score_ticks: int
    score: float
    enter_event: bool
    exit_event: bool
    execution_lock: bool


def disruption_score(m: SurvivalMetrics) -> float:
    t = max(0.0, min(1.0, float(m.ams_toxicity_0_1)))
    return min(1.0e6, abs(float(m.drift_z)) + abs(float(m.tsfm_residual_z)) + 4.0 * t)


def _survival_step_py(
    prev_in_survival: bool,
    consec_low: int,
    m: SurvivalMetrics,
    params: SurvivalKernelParams,
) -> SurvivalTickResult:
    score = disruption_score(m)
    in_survival = prev_in_survival
    consec = consec_low
    enter = False
    exit_ev = False
    if prev_in_survival:
        if score < params.exit_threshold:
            consec = consec + 1
        else:
            consec = 0
        if consec >= params.exit_hysteresis_ticks:
            in_survival = False
            consec = 0
            exit_ev = True
    elif score >= params.enter_threshold:
        in_survival = True
        consec = 0
        enter = True
    else:
        consec = 0
    return SurvivalTickResult(
        in_survival=in_survival,
        consec_low_score_ticks=consec,
        score=score,
        enter_event=enter,
        exit_event=exit_ev,
        execution_lock=in_survival,
    )


class _SurvivalKernelParamsC(ctypes.Structure):
    _fields_ = [
        ("enter_threshold", ctypes.c_double),
        ("exit_threshold", ctypes.c_double),
        ("exit_hysteresis_ticks", ctypes.c_uint32),
    ]


class _SurvivalKernelIoC(ctypes.Structure):
    _fields_ = [
        ("drift_z", ctypes.c_double),
        ("tsfm_residual_z", ctypes.c_double),
        ("ams_toxicity_0_1", ctypes.c_double),
        ("in_survival_prev", ctypes.c_uint32),
        ("consec_low_score_ticks", ctypes.c_uint32),
        ("score_out", ctypes.c_double),
        ("in_survival_out", ctypes.c_uint32),
        ("enter_event", ctypes.c_uint32),
        ("exit_event", ctypes.c_uint32),
        ("execution_lock_out", ctypes.c_uint32),
    ]


_rust_eval: Any | None = None


def _load_rust_eval() -> Any | None:
    global _rust_eval
    if _rust_eval is not None:
        return _rust_eval
    path = (os.environ.get(SURVIVAL_LIB_ENV) or "").strip()
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        logger.debug("survival_kernel rust lib nicht gefunden: %s", path)
        return None
    try:
        lib = ctypes.CDLL(str(p))
    except OSError as exc:
        logger.warning("survival_kernel CDLL failed: %s", exc)
        return None
    fn = lib.survival_kernel_evaluate_io
    fn.argtypes = [ctypes.POINTER(_SurvivalKernelIoC), ctypes.POINTER(_SurvivalKernelParamsC)]
    fn.restype = None
    _rust_eval = fn
    return _rust_eval


def _survival_step_rust(
    prev_in_survival: bool,
    consec_low: int,
    m: SurvivalMetrics,
    params: SurvivalKernelParams,
) -> SurvivalTickResult | None:
    fn = _load_rust_eval()
    if fn is None:
        return None
    pc = _SurvivalKernelParamsC(
        enter_threshold=params.enter_threshold,
        exit_threshold=params.exit_threshold,
        exit_hysteresis_ticks=int(params.exit_hysteresis_ticks),
    )
    io = _SurvivalKernelIoC(
        drift_z=float(m.drift_z),
        tsfm_residual_z=float(m.tsfm_residual_z),
        ams_toxicity_0_1=float(m.ams_toxicity_0_1),
        in_survival_prev=1 if prev_in_survival else 0,
        consec_low_score_ticks=int(consec_low),
    )
    fn(ctypes.byref(io), ctypes.byref(pc))
    return SurvivalTickResult(
        in_survival=bool(io.in_survival_out),
        consec_low_score_ticks=int(io.consec_low_score_ticks),
        score=float(io.score_out),
        enter_event=bool(io.enter_event),
        exit_event=bool(io.exit_event),
        execution_lock=bool(io.execution_lock_out),
    )


def survival_tick(
    prev_in_survival: bool,
    consec_low: int,
    m: SurvivalMetrics,
    params: SurvivalKernelParams | None = None,
) -> SurvivalTickResult:
    p = params or SurvivalKernelParams()
    rust = _survival_step_rust(prev_in_survival, consec_low, m, p)
    if rust is not None:
        return rust
    return _survival_step_py(prev_in_survival, consec_low, m, p)


def read_survival_state_from_redis(redis: Redis | None) -> dict[str, Any] | None:
    if redis is None:
        return None
    try:
        raw = redis.get(SURVIVAL_REDIS_KEY)
    except Exception as exc:
        logger.warning("survival redis read failed: %s", exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def write_survival_state_to_redis(redis: Redis | None, state: dict[str, Any]) -> None:
    if redis is None:
        return
    try:
        redis.set(SURVIVAL_REDIS_KEY, json.dumps(state, separators=(",", ":")))
    except Exception as exc:
        logger.warning("survival redis write failed: %s", exc)


def env_survival_forced() -> bool:
    return os.environ.get(SURVIVAL_ENV_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def merge_survival_truth(
    base: dict[str, Any],
    *,
    redis: Redis | None = None,
) -> dict[str, Any]:
    out = dict(base)
    st = read_survival_state_from_redis(redis)
    active = bool(st.get("active")) if isinstance(st, dict) else False
    if env_survival_forced():
        active = True
    out["survival_mode_active"] = active
    out["survival_execution_lock"] = active
    out["survival_leverage_cap_1x"] = active
    out["survival_delta_hedge_requested"] = active
    if isinstance(st, dict):
        out["survival_kernel_score"] = st.get("score")
        out["survival_kernel_consec_low"] = st.get("consec_low_score_ticks")
    return out


def apply_survival_signal_overrides(signal_payload: dict[str, Any]) -> dict[str, Any]:
    sp = dict(signal_payload)
    reasons = list(sp.get("leverage_cap_reasons_json") or [])
    tag = "survival_mode_portfolio_governor_1x"
    if tag not in reasons:
        reasons.append(tag)
    sp["allowed_leverage"] = 1
    sp["recommended_leverage"] = 1
    sp["execution_leverage_cap"] = 1
    sp["leverage_cap_reasons_json"] = reasons
    sp["survival_mode_active"] = True
    return sp


def build_safety_incident_diagnosis_survival(
    *,
    metrics: SurvivalMetrics,
    score: float,
    entered: bool,
    exited: bool,
) -> dict[str, Any]:
    """Payload passend zu shared/contracts/schemas/safety_incident_diagnosis.schema.json."""
    phase = "Eintritt" if entered else ("Austritt" if exited else "Fortlaufend")
    summary = (
        f"Survival-Mode ({phase}): Disruption-Score={score:.3f} "
        f"(drift_z={metrics.drift_z:.3f}, tsfm_z={metrics.tsfm_residual_z:.3f}, "
        f"ams_tox={metrics.ams_toxicity_0_1:.3f}). "
        "Stabilitaet vor Profitabilitaet: Hebel-Floor 1x, Execution-Lock fuer neue Richtungen."
    )
    return {
        "schema_version": "1.0",
        "execution_authority": "none",
        "incident_summary_de": summary[:6000],
        "root_causes_de": [
            "Kombinierter Ausreisser in Drift-, TimesFM-Residual- und/oder AMS-Stresssignalen "
            "(Black-Swan-Detektor ueber Schwellenwert)."
        ],
        "affected_services_de": [
            "live-broker (Execution, Hebel-Cap)",
            "signal-engine / portfolio_risk_governor (indirekt ueber Signal-Overrides)",
            "alert-engine (Telegram-Ausleitung)",
        ],
        "recommended_next_steps_de": [
            "Regime stabil beobachten bis Hysterese-Safe-Exit greift.",
            "Bestand und Margin pruefen; Delta-Hedge-Vorschlag im Operator-Intel pruefen.",
            "Nach Exit: Ursachen in inference-server / adversarial-engine Logs verifizieren.",
        ],
        "proposed_commands_de": [
            "redis-cli GET ops:survival_kernel:v1",
            "unset BITGET_SURVIVAL_MODE   # nur in kontrollierten Testumgebungen",
        ],
        "env_or_config_hints_de": [
            SURVIVAL_ENV_FLAG,
            SURVIVAL_LIB_ENV,
            SURVIVAL_REDIS_KEY,
        ],
        "non_authoritative_note_de": (
            "Diese Struktur ist eine KI-/Systemdiagnose ohne Ausfuehrungsbefugnis; "
            "keine automatischen Shell-Befehle."
        ),
        "separation_note_de": (
            "SafetyIncidentDiagnosis ist rein analytisch; Live-Orders und Limits werden "
            "ausschliesslich ueber survival_kernel-Zustand und live-broker-Pfade gesteuert."
        ),
    }


def _persist_tick_state(redis: Redis | None, tr: SurvivalTickResult) -> None:
    write_survival_state_to_redis(
        redis,
        {
            "active": tr.in_survival,
            "score": tr.score,
            "consec_low_score_ticks": tr.consec_low_score_ticks,
            "execution_lock": tr.execution_lock,
            "updated_ts_ms": int(time.time() * 1000),
        },
    )


def process_survival_metrics(
    *,
    metrics: SurvivalMetrics,
    redis: Redis | None,
    params: SurvivalKernelParams | None = None,
    bus: Any | None = None,
    hedge_symbol: str = "BTCUSDT",
) -> SurvivalTickResult:
    st = read_survival_state_from_redis(redis) or {}
    prev = bool(st.get("active")) if isinstance(st, dict) else False
    consec = int(st.get("consec_low_score_ticks") or 0) if isinstance(st, dict) else 0
    if env_survival_forced():
        tr = SurvivalTickResult(
            in_survival=True,
            consec_low_score_ticks=0,
            score=disruption_score(metrics),
            enter_event=not prev,
            exit_event=False,
            execution_lock=True,
        )
        _persist_tick_state(redis, tr)
    else:
        tr = survival_tick(prev, consec, metrics, params)
        _persist_tick_state(redis, tr)
    if bus is not None and (tr.enter_event or tr.exit_event):
        diag = build_safety_incident_diagnosis_survival(
            metrics=metrics,
            score=tr.score,
            entered=tr.enter_event,
            exited=tr.exit_event,
        )
        publish_survival_system_events(bus, diagnosis=diag, metrics=metrics, tr=tr)
    if bus is not None and tr.enter_event:
        publish_survival_hedge_operator_intel(bus, symbol=hedge_symbol)
    return tr


def publish_survival_system_events(
    bus: Any,
    *,
    diagnosis: dict[str, Any],
    metrics: SurvivalMetrics,
    tr: SurvivalTickResult,
) -> None:
    """Publiziert system_alert fuer alert-engine (Telegram)."""
    if not tr.enter_event and not tr.exit_event:
        return
    if tr.enter_event:
        alert_key = SYSTEM_ENTER_SURVIVAL_MODE
        title = "SYSTEM_ENTER_SURVIVAL_MODE"
        msg = (
            f"Survival aktiv (Score={tr.score:.3f}). "
            f"Drift z={metrics.drift_z:.2f}, TSFM z={metrics.tsfm_residual_z:.2f}, "
            f"AMS tox={metrics.ams_toxicity_0_1:.2f}."
        )
    else:
        alert_key = SYSTEM_EXIT_SURVIVAL_MODE
        title = "SYSTEM_EXIT_SURVIVAL_MODE"
        msg = f"Survival beendet nach Hysterese (Score={tr.score:.3f})."
    env = EventEnvelope(
        event_type="system_alert",
        dedupe_key=f"{alert_key}:{int(time.time() // 60)}",
        payload={
            "alert_key": alert_key,
            "severity": "critical" if tr.enter_event else "warn",
            "title": title,
            "message": msg,
            "dedupe_ttl_minutes": 2,
            "details": {
                "survival_kernel": {
                    "score": tr.score,
                    "metrics": {
                        "drift_z": metrics.drift_z,
                        "tsfm_residual_z": metrics.tsfm_residual_z,
                        "ams_toxicity_0_1": metrics.ams_toxicity_0_1,
                    },
                    "execution_lock": tr.execution_lock,
                },
                "safety_incident_diagnosis": diagnosis,
            },
        },
        trace={"source": "survival-kernel"},
    )
    bus.publish(STREAM_SYSTEM_ALERT, env)


def publish_survival_hedge_operator_intel(bus: Any, *, symbol: str) -> None:
    """Aggressives Hedging: Hinweis/Delta-Gegenposition — keine Order ohne zusaetzliche Policy."""
    try:
        from shared_py.operator_intel import build_operator_intel_envelope_payload
    except ImportError:
        return
    pl = build_operator_intel_envelope_payload(
        intel_kind="risk_notice",
        symbol=symbol,
        correlation_id="survival:delta-hedge",
        severity="critical",
        text=(
            "Survival-Mode: automatischer Delta-Hedge-Vorschlag — "
            "Gegenposition / neutrales Overlay pruefen (kein Autosubmit)."
        ),
        reasons=["survival_delta_hedge_stub"],
        dedupe_key="survival:hedge:notice",
        dedupe_ttl_minutes=5,
    )
    from shared_py.eventbus.envelope import STREAM_OPERATOR_INTEL

    env = EventEnvelope(
        event_type="operator_intel",
        symbol=symbol,
        payload=pl,
        trace={"source": "survival-kernel"},
    )
    bus.publish(STREAM_OPERATOR_INTEL, env)
