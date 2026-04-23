from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from shared_py.eventbus import EventEnvelope
from shared_py.operator_intel import format_operator_intel_message, redact_operator_intel_payload

from alert_engine.alerts import formatter
from alert_engine.config import Settings
from alert_engine.storage.repo_structure import RepoStructureTrend

logger = logging.getLogger("alert_engine.policies")


@dataclass(frozen=True)
class AlertIntent:
    alert_type: str
    severity: str
    dedupe_key: str | None
    dedupe_ttl_minutes: int
    symbol: str | None
    timeframe: str | None
    text: str
    payload: dict[str, Any]


def _ts_bucket_ms(ts_ms: int, window_minutes: int) -> int:
    w = max(1, window_minutes) * 60 * 1000
    return ts_ms // w


def _num(payload: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = payload.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def evaluate_signal_created(env: EventEnvelope, settings: Settings) -> list[AlertIntent]:
    p = env.payload
    sym = env.symbol
    tf = env.timeframe or str(p.get("timeframe") or "")
    strength = _num(p, "signal_strength_0_100")
    sclass = str(p.get("signal_class") or "").lower()
    analysis_ts = int(p.get("analysis_ts_ms") or env.exchange_ts_ms or env.ingest_ts_ms)
    direction = str(p.get("direction") or "?")
    prob = _num(p, "probability_0_1")
    reasons = formatter.top_reasons_short(p, 3)
    stop_s = formatter.stop_summary_from_payload(p)
    reasons_txt = "; ".join(reasons) if reasons else "—"

    gross_hit = sclass == "gross" or strength >= settings.alert_signal_gross_threshold
    core_hit = sclass == "kern" or strength >= settings.alert_signal_core_threshold

    out: list[AlertIntent] = []
    if gross_hit:
        bucket = _ts_bucket_ms(analysis_ts, settings.alert_dedupe_minutes_gross)
        dk = f"gross:{sym}:{tf}:{bucket}"
        text = (
            f"GROSS-Signal {sym} {tf}\n"
            f"dir={direction} strength={strength:.0f} p={prob:.2f}\n"
            f"{stop_s}\n"
            f"reasons: {reasons_txt}"
        )
        out.append(
            AlertIntent(
                alert_type="GROSS_SIGNAL",
                severity="critical",
                dedupe_key=dk,
                dedupe_ttl_minutes=settings.alert_dedupe_minutes_gross,
                symbol=sym,
                timeframe=tf or None,
                text=formatter.escape_for_plain(text),
                payload={"raw_event_id": env.event_id, "signal_id": p.get("signal_id")},
            )
        )
        logger.info("policy matched: GROSS_SIGNAL symbol=%s", sym)
    elif core_hit:
        bucket = _ts_bucket_ms(analysis_ts, settings.alert_dedupe_minutes_core)
        dk = f"core:{sym}:{tf}:{bucket}"
        text = (
            f"KERN-Signal {sym} {tf}\n"
            f"dir={direction} strength={strength:.0f} p={prob:.2f}\n"
            f"{stop_s}\n"
            f"reasons: {reasons_txt}"
        )
        out.append(
            AlertIntent(
                alert_type="CORE_SIGNAL",
                severity="warn",
                dedupe_key=dk,
                dedupe_ttl_minutes=settings.alert_dedupe_minutes_core,
                symbol=sym,
                timeframe=tf or None,
                text=formatter.escape_for_plain(text),
                payload={"raw_event_id": env.event_id, "signal_id": p.get("signal_id")},
            )
        )
        logger.info("policy matched: CORE_SIGNAL symbol=%s", sym)

    live_blocks = p.get("live_execution_block_reasons_json") or []
    if (
        isinstance(live_blocks, list)
        and live_blocks
        and str(p.get("trade_action") or "").strip().lower() == "allow_trade"
    ):
        bucket = _ts_bucket_ms(analysis_ts, max(1, settings.alert_dedupe_minutes_core))
        dk = f"live_exec_policy:{sym}:{tf}:{bucket}"
        top = ", ".join(str(x) for x in live_blocks[:4])
        text = (
            f"Live-Execution blockiert (Konto/Portfolio), Signal bleibt allow_trade fuer Paper/Shadow\n"
            f"{sym} {tf} dir={direction}\n"
            f"live_execution_block: {top}"
        )
        out.append(
            AlertIntent(
                alert_type="LIVE_EXECUTION_POLICY_WARN",
                severity="warn",
                dedupe_key=dk,
                dedupe_ttl_minutes=max(1, settings.alert_dedupe_minutes_core),
                symbol=sym,
                timeframe=tf or None,
                text=formatter.escape_for_plain(text),
                payload={
                    "raw_event_id": env.event_id,
                    "signal_id": p.get("signal_id"),
                    "live_execution_block_reasons_json": live_blocks[:12],
                },
            )
        )
        logger.info("policy matched: LIVE_EXECUTION_POLICY_WARN symbol=%s", sym)
    return out


def evaluate_structure_updated(
    env: EventEnvelope, settings: Settings, trend_repo: RepoStructureTrend
) -> list[AlertIntent]:
    p = env.payload
    sym = env.symbol
    tf = env.timeframe or str(p.get("timeframe") or "")
    if not tf:
        return []
    new_trend = str(p.get("trend_dir") or "")
    ts_ms = int(p.get("ts_ms") or env.exchange_ts_ms or env.ingest_ts_ms)
    choch = str(p.get("event_subtype") or p.get("kind") or "").upper() == "CHOCH"
    if not choch and p.get("choch") is True:
        choch = True

    old = trend_repo.get_last_trend(sym, tf)
    flip = bool(old and new_trend and old != new_trend)
    trend_repo.set_trend(sym, tf, new_trend or old or "unknown", ts_ms)

    if not (choch or flip):
        return []

    dk = f"trend:{sym}:{tf}:{_ts_bucket_ms(ts_ms, settings.alert_dedupe_minutes_trend)}"
    text = (
        f"Struktur / Richtung {sym} {tf}\n"
        f"CHOCH={choch} trend {old!r} -> {new_trend!r}"
    )
    logger.info("policy matched: TREND_WARN symbol=%s flip=%s choch=%s", sym, flip, choch)
    return [
        AlertIntent(
            alert_type="TREND_WARN",
            severity="warn",
            dedupe_key=dk,
            dedupe_ttl_minutes=settings.alert_dedupe_minutes_trend,
            symbol=sym,
            timeframe=tf,
            text=formatter.escape_for_plain(text),
            payload={"raw_event_id": env.event_id},
        )
    ]


def evaluate_trade_closed(env: EventEnvelope) -> list[AlertIntent]:
    p = env.payload
    sym = env.symbol
    pid = str(p.get("position_id") or "")
    reason = str(p.get("reason") or "")
    pnl = p.get("pnl_net_usdt")
    fees = p.get("fees_total_usdt")
    funding = p.get("funding_total_usdt")
    text = (
        f"Trade geschlossen {sym}\n"
        f"position={pid}\n"
        f"reason={reason}\n"
        f"pnl_net={pnl}\n"
        f"fees={fees} funding={funding}"
    )
    logger.info("policy matched: TRADE_CLOSED symbol=%s", sym)
    return [
        AlertIntent(
            alert_type="TRADE_CLOSED",
            severity="info",
            dedupe_key=None,
            dedupe_ttl_minutes=0,
            symbol=sym,
            timeframe=None,
            text=formatter.escape_for_plain(text),
            payload={"raw_event_id": env.event_id, "position_id": pid},
        )
    ]


def evaluate_risk_alert(env: EventEnvelope) -> list[AlertIntent]:
    p = env.payload
    sym = env.symbol
    sev_raw = str(p.get("severity") or "").lower()
    warnings = p.get("warnings") or []
    sq = int(p.get("stop_quality_score") or 0)
    wtxt = ", ".join(str(x) for x in warnings) if isinstance(warnings, list) else str(warnings)
    if sev_raw in ("high", "critical"):
        severity = "critical" if sev_raw == "critical" else "warn"
    elif sq <= 50 and len(wtxt) > 0:
        severity = "critical"
    else:
        severity = "warn"
    text = f"Stop / Risk {sym}\nstop_quality={sq}\n{wtxt}"
    logger.info("policy matched: STOP_DANGER symbol=%s", sym)
    return [
        AlertIntent(
            alert_type="STOP_DANGER",
            severity=severity,
            dedupe_key=None,
            dedupe_ttl_minutes=0,
            symbol=sym,
            timeframe=None,
            text=formatter.escape_for_plain(text),
            payload={"raw_event_id": env.event_id},
        )
    ]


def evaluate_news_scored(env: EventEnvelope, settings: Settings) -> list[AlertIntent]:
    p = env.payload
    score = int(p.get("relevance_score") or 0)
    impact = str(p.get("impact_window") or "")
    if score < settings.alert_news_threshold or impact != "immediate":
        return []
    news_id = str(p.get("news_id") or "")
    sent = str(p.get("sentiment") or "")
    title = str(p.get("title") or news_id)
    url = str(p.get("url") or "")
    url_d = formatter.shorten_url_display(url) if url else "—"
    bucket = _ts_bucket_ms(
        int(env.ingest_ts_ms), settings.alert_dedupe_minutes_news
    )
    dk = f"news:{news_id}:{bucket}"
    text = f"News HIGH {score}/100 {sent}\n{title}\n{url_d}"
    logger.info("policy matched: NEWS_HIGH news_id=%s", news_id)
    return [
        AlertIntent(
            alert_type="NEWS_HIGH",
            severity="warn",
            dedupe_key=dk,
            dedupe_ttl_minutes=settings.alert_dedupe_minutes_news,
            symbol=env.symbol,
            timeframe=None,
            text=formatter.escape_for_plain(text),
            payload={"raw_event_id": env.event_id, "news_id": news_id},
        )
    ]


def evaluate_system_alert(env: EventEnvelope) -> list[AlertIntent]:
    p = env.payload
    msg = str(p.get("message") or p.get("text") or env.event_id)
    sev = str(p.get("severity") or "warn").lower()
    if sev not in ("info", "warn", "critical"):
        sev = "warn"
    alert_key = (
        p.get("alert_key")
        if isinstance(p.get("alert_key"), str)
        else (env.dedupe_key if isinstance(env.dedupe_key, str) else None)
    )
    title = str(p.get("title") or "").strip()
    details = p.get("details") if isinstance(p.get("details"), dict) else {}
    dk = (
        p.get("dedupe_key")
        if isinstance(p.get("dedupe_key"), str)
        else (env.dedupe_key if isinstance(env.dedupe_key, str) else None)
    )
    ttl = int(p.get("dedupe_ttl_minutes") or 10) if dk else 0
    alert_type = _system_alert_type(alert_key)
    prefix = f"{title}: " if title else "System: "
    logger.info("policy matched: SYSTEM_ALERT")
    return [
        AlertIntent(
            alert_type=alert_type,
            severity=sev,
            dedupe_key=dk,
            dedupe_ttl_minutes=ttl,
            symbol=env.symbol,
            timeframe=env.timeframe,
            text=formatter.escape_for_plain(f"{prefix}{msg}"),
            payload={
                "raw_event_id": env.event_id,
                "alert_key": alert_key,
                "title": title or None,
                "details": details,
            },
        )
    ]


def _system_alert_type(alert_key: str | None) -> str:
    key = (alert_key or "").strip().lower()
    if key == "system_enter_survival_mode":
        return "SYSTEM_ENTER_SURVIVAL_MODE"
    if key == "system_exit_survival_mode":
        return "SYSTEM_EXIT_SURVIVAL_MODE"
    if key.startswith("live-broker:kill-switch"):
        return "LIVE_BROKER_KILL_SWITCH"
    if key.startswith("live-broker:flatten"):
        return "LIVE_BROKER_EMERGENCY_FLATTEN"
    if key.startswith("live-broker:order-timeout"):
        return "LIVE_BROKER_ORDER_TIMEOUT"
    if key.startswith("live-broker:reconcile") or key.startswith("svc:live-broker:reconcile"):
        return "LIVE_BROKER_RECONCILE"
    if key.startswith("svc:live-broker:"):
        return "LIVE_BROKER_MONITOR"
    return "SYSTEM_ALERT"


_INTEL_KIND_ALERT: dict[str, str] = {
    "self_healing_proposal": "OPERATOR_INCIDENT",
    "pre_trade_rationale": "OPERATOR_PRE_TRADE",
    "release_pending": "OPERATOR_RELEASE_PENDING",
    "trade_open": "OPERATOR_TRADE_OPEN",
    "trade_close": "OPERATOR_TRADE_CLOSE",
    "exit_rationale": "OPERATOR_EXIT",
    "incident": "OPERATOR_INCIDENT",
    "kill_switch": "LIVE_BROKER_KILL_SWITCH",
    "safety_latch": "OPERATOR_SAFETY_LATCH",
    "strategy_intent": "OPERATOR_STRATEGY_INTENT",
    "no_trade": "OPERATOR_NO_TRADE",
    "plan_summary": "OPERATOR_PLAN_SUMMARY",
    "risk_notice": "OPERATOR_RISK_NOTICE",
    "fill": "OPERATOR_FILL",
    "exit_result": "OPERATOR_EXIT",
    "post_trade_review": "OPERATOR_POST_TRADE",
    "execution_update": "OPERATOR_EXECUTION_UPDATE",
}


def evaluate_operator_intel(
    env: EventEnvelope,
    settings: Settings,
    redis_client: Any,
) -> list[AlertIntent]:
    p = redact_operator_intel_payload(dict(env.payload))
    kind = str(p.get("intel_kind") or "execution_update").strip().lower()
    alert_type = _INTEL_KIND_ALERT.get(kind, "OPERATOR_EXECUTION_UPDATE")
    sev = str(p.get("severity") or "info").lower()
    if sev not in ("info", "warn", "critical"):
        sev = "warn"
    text = str(p.get("text") or "").strip() or format_operator_intel_message(p)
    text = formatter.escape_for_plain(text)
    dk = p.get("dedupe_key") if isinstance(p.get("dedupe_key"), str) else None
    ttl = int(p.get("dedupe_ttl_minutes") or 0)
    reply_to = p.get("reply_to_telegram_message_id")
    cid = p.get("correlation_id") if isinstance(p.get("correlation_id"), str) else None
    if reply_to is None and cid and redis_client is not None:
        try:
            raw = redis_client.get(f"ae:opintel:thread:{cid}")
            if raw is not None:
                reply_to = int(raw)
        except (TypeError, ValueError):
            reply_to = None
    if reply_to is not None:
        try:
            p["reply_to_telegram_message_id"] = int(reply_to)
        except (TypeError, ValueError):
            pass
    logger.info("policy matched: %s intel_kind=%s", alert_type, kind)
    return [
        AlertIntent(
            alert_type=alert_type,
            severity=sev,
            dedupe_key=dk,
            dedupe_ttl_minutes=max(1, ttl) if dk else 0,
            symbol=env.symbol,
            timeframe=env.timeframe,
            text=text,
            payload={
                "raw_event_id": env.event_id,
                **p,
                "text": text,
            },
        )
    ]


def evaluate_envelope(
    env: EventEnvelope,
    settings: Settings,
    trend_repo: RepoStructureTrend,
    redis_client: Any = None,
) -> list[AlertIntent]:
    et = env.event_type
    if et == "signal_created":
        return evaluate_signal_created(env, settings)
    if et == "structure_updated":
        return evaluate_structure_updated(env, settings, trend_repo)
    if et == "trade_closed":
        return evaluate_trade_closed(env)
    if et == "risk_alert":
        return evaluate_risk_alert(env)
    if et == "news_scored":
        return evaluate_news_scored(env, settings)
    if et == "system_alert":
        return evaluate_system_alert(env)
    if et == "operator_intel":
        return evaluate_operator_intel(env, settings, redis_client)
    return []
