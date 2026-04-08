"""
Integrationsmatrix (PROMPT 21): logische externe Zusammenhaenge, Feature-Flags,
Health aus Probes, sichere Credential-Referenzen (nur Namen, keine Werte).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# Reihenfolge: schlechtester Status gewinnt
_STATUS_RANK = {
    "error": 0,
    "misconfigured": 1,
    "degraded": 2,
    "not_configured": 3,
    "disabled": 4,
    "ok": 5,
}


def _worst_status(*statuses: str) -> str:
    best = "ok"
    best_r = 99
    for s in statuses:
        r = _STATUS_RANK.get(s, 10)
        if r < best_r:
            best_r = r
            best = s
    return best


def _svc_status(svc: dict[str, Any] | None) -> str:
    if not svc:
        return "not_configured"
    if not svc.get("configured", True):
        return "not_configured"
    return str(svc.get("status") or "error")


def _svc_error_public(svc: dict[str, Any] | None) -> str | None:
    if not svc:
        return "Service nicht konfiguriert"
    if svc.get("status") == "not_configured":
        return "Health-URL nicht konfiguriert"
    d = svc.get("detail")
    if d:
        return str(d)[:500]
    http = svc.get("http_status")
    if svc.get("status") == "degraded" and http:
        return f"HTTP {http}"
    fc = svc.get("failed_checks")
    if isinstance(fc, list) and fc:
        return "; ".join(str(x) for x in fc[:5])[:500]
    return None


def build_integrations_matrix_payload(
    g: Any,
    services: list[dict[str, Any]],
    *,
    database_status: str,
    redis_status: str | None,
    ops_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Gibt (api_rows, upsert_batch) zurueck.
    api_rows enthalten Feature-Flags und Referenzen; upsert_batch fuer DB.
    """
    by_name = {str(s.get("name")): s for s in services}

    monitor_ops = ops_summary.get("monitor") if isinstance(ops_summary, dict) else {}
    open_alerts = 0
    if isinstance(monitor_ops, dict):
        open_alerts = int(monitor_ops.get("open_alert_count") or 0)
    alert_ops = ops_summary.get("alert_engine") if isinstance(ops_summary, dict) else {}
    outbox_failed = 0
    if isinstance(alert_ops, dict):
        outbox_failed = int(alert_ops.get("outbox_failed") or 0)

    api_rows: list[dict[str, Any]] = []
    upsert: list[dict[str, Any]] = []

    # --- Broker / Exchange ---
    paper = by_name.get("paper-broker")
    live_b = by_name.get("live-broker")
    market = by_name.get("market-stream")
    br_st = _worst_status(
        _svc_status(paper),
        _svc_status(live_b),
        _svc_status(market),
    )
    br_err = None
    for svc, label in (
        (paper, "paper-broker"),
        (live_b, "live-broker"),
        (market, "market-stream"),
    ):
        if _svc_status(svc) in ("error", "degraded", "not_configured"):
            br_err = _svc_error_public(svc)
            if br_err:
                br_err = f"{label}: {br_err}"
            break
    live_explicit = bool(g.live_trade_enable and g.live_order_submission_enabled)
    api_rows.append(
        {
            "integration_key": "broker_exchange",
            "display_name_de": "Broker / Boerse (Bitget)",
            "display_name_en": "Broker / exchange (Bitget)",
            "feature_flags": {
                "execution_mode": g.execution_mode,
                "live_broker_enabled": g.live_broker_enabled,
                "live_trade_enable": g.live_trade_enable,
                "live_order_submission_enabled": g.live_order_submission_enabled,
                "paper_path_active": g.paper_path_active,
                "shadow_trade_enable": g.shadow_trade_enable,
                "bitget_demo_enabled": bool(getattr(g, "bitget_demo_enabled", False)),
            },
            "live_access": {
                "live_orders_explicitly_enabled": live_explicit,
                "note_de": (
                    "Live-Zugriff nur bei EXECUTION_MODE=live, LIVE_BROKER_ENABLED und "
                    "expliziten LIVE_TRADE_ENABLE / Order-Submission-Flags."
                ),
            },
            "credential_refs": [
                "env:BITGET_API_KEY",
                "env:BITGET_API_SECRET",
                "env:BITGET_PASSPHRASE",
                "vault:bitget_api (optional, wenn VAULT_MODE aktiv)",
            ],
            "health_probes": {
                "market_stream": _svc_status(market),
                "paper_broker": _svc_status(paper),
                "live_broker": _svc_status(live_b),
            },
            "health_status": br_st,
            "health_error_public": br_err,
        }
    )
    upsert.append(
        {
            "integration_key": "broker_exchange",
            "health_status": br_st,
            "error_public": br_err,
            "probe_detail": {
                "market_stream": _svc_status(market),
                "paper_broker": _svc_status(paper),
                "live_broker": _svc_status(live_b),
            },
        }
    )

    # --- Marktdaten- & Signal-Pipeline (Engines) ---
    fe = by_name.get("feature-engine")
    struct_e = by_name.get("structure-engine")
    sig_eng = by_name.get("signal-engine")
    draw_e = by_name.get("drawing-engine")
    news_e = by_name.get("news-engine")
    pipe_st = _worst_status(
        _svc_status(fe),
        _svc_status(struct_e),
        _svc_status(sig_eng),
        _svc_status(draw_e),
        _svc_status(news_e),
    )
    pipe_err: str | None = None
    for svc, label in (
        (fe, "feature-engine"),
        (struct_e, "structure-engine"),
        (sig_eng, "signal-engine"),
        (draw_e, "drawing-engine"),
        (news_e, "news-engine"),
    ):
        st = _svc_status(svc)
        if st in ("error", "degraded", "not_configured"):
            detail = _svc_error_public(svc)
            pipe_err = f"{label}: {detail}" if detail else f"{label}: {st}"
            break
    api_rows.append(
        {
            "integration_key": "signal_pipeline",
            "display_name_de": "Marktdaten- & Signal-Pipeline",
            "display_name_en": "Market data & signal pipeline",
            "feature_flags": {},
            "credential_refs": [
                "env:HEALTH_URL_FEATURE_ENGINE",
                "env:HEALTH_URL_STRUCTURE_ENGINE",
                "env:HEALTH_URL_SIGNAL_ENGINE",
                "env:HEALTH_URL_DRAWING_ENGINE",
                "env:HEALTH_URL_NEWS_ENGINE",
            ],
            "health_probes": {
                "feature_engine": _svc_status(fe),
                "structure_engine": _svc_status(struct_e),
                "signal_engine": _svc_status(sig_eng),
                "drawing_engine": _svc_status(draw_e),
                "news_engine": _svc_status(news_e),
            },
            "health_status": pipe_st,
            "health_error_public": pipe_err,
        }
    )
    upsert.append(
        {
            "integration_key": "signal_pipeline",
            "health_status": pipe_st,
            "error_public": pipe_err,
            "probe_detail": {
                "feature_engine": _svc_status(fe),
                "structure_engine": _svc_status(struct_e),
                "signal_engine": _svc_status(sig_eng),
                "drawing_engine": _svc_status(draw_e),
                "news_engine": _svc_status(news_e),
            },
        }
    )

    # --- Learning (Scores, Drift, Registry-Pfade ueber Gateway-Proxies) ---
    learn = by_name.get("learning-engine")
    learn_st = _svc_status(learn)
    learn_err = _svc_error_public(learn) if learn_st != "ok" else None
    api_rows.append(
        {
            "integration_key": "learning_engine",
            "display_name_de": "Learning / Registry & Drift",
            "display_name_en": "Learning / registry & drift",
            "feature_flags": {},
            "credential_refs": [
                "env:HEALTH_URL_LEARNING_ENGINE",
                "gateway:GET /v1/learning/* (Proxies)",
            ],
            "health_probes": {"learning_engine": _svc_status(learn)},
            "health_status": learn_st,
            "health_error_public": learn_err,
        }
    )
    upsert.append(
        {
            "integration_key": "learning_engine",
            "health_status": learn_st,
            "error_public": learn_err,
            "probe_detail": {"learning_engine": _svc_status(learn)},
        }
    )

    # --- Telegram (Zustellung ueber alert-engine) ---
    ae = by_name.get("alert-engine")
    tg_st = _svc_status(ae)
    tg_err = _svc_error_public(ae) if tg_st != "ok" else None
    if tg_st == "ok" and outbox_failed > 0:
        tg_st = "degraded"
        tg_err = f"alert_outbox_failed_count={outbox_failed}"
    api_rows.append(
        {
            "integration_key": "telegram",
            "display_name_de": "Telegram (Alerts / Kunden)",
            "display_name_en": "Telegram (alerts / customers)",
            "feature_flags": {
                "telegram_dry_run": g.telegram_dry_run,
                "telegram_bot_username_configured": bool(
                    str(getattr(g, "telegram_bot_username", "") or "").strip()
                ),
                "commercial_telegram_required_for_console": getattr(
                    g, "commercial_telegram_required_for_console", False
                ),
            },
            "credential_refs": [
                "env:TELEGRAM_BOT_TOKEN",
                "env:TELEGRAM_WEBHOOK_SECRET",
            ],
            "health_probes": {"alert_engine": _svc_status(ae)},
            "health_status": tg_st,
            "health_error_public": tg_err,
            "ops_hint": {"alert_outbox_failed": outbox_failed},
        }
    )
    upsert.append(
        {
            "integration_key": "telegram",
            "health_status": tg_st,
            "error_public": tg_err,
            "probe_detail": {
                "alert_engine": _svc_status(ae),
                "outbox_failed": outbox_failed,
            },
        }
    )

    # --- Zahlungsprovider ---
    pay_enabled = bool(getattr(g, "payment_checkout_enabled", False))
    if not pay_enabled:
        pay_st = "disabled"
        pay_err = None
        pay_detail = {"checkout": "disabled"}
    else:
        stripe_on = bool(getattr(g, "payment_stripe_enabled", False))
        mock_on = bool(getattr(g, "payment_mock_enabled", False))
        mode = g.payment_environment()
        pay_st = "ok"
        pay_err = None
        if stripe_on and mode == "live":
            sk = str(getattr(g, "payment_stripe_secret_key", "") or "").strip()
            wh = str(getattr(g, "payment_stripe_webhook_secret", "") or "").strip()
            if not sk or not wh:
                pay_st = "misconfigured"
                pay_err = "Stripe live: Secret/Webhook-Secret fehlen oder zu kurz"
        pay_detail = {
            "checkout_enabled": True,
            "stripe_enabled": stripe_on,
            "mock_enabled": mock_on,
            "environment": mode,
        }
    api_rows.append(
        {
            "integration_key": "payment_provider",
            "display_name_de": "Zahlungsprovider (Stripe / Mock)",
            "display_name_en": "Payment provider (Stripe / mock)",
            "feature_flags": {
                "payment_checkout_enabled": pay_enabled,
                "payment_stripe_enabled": bool(
                    getattr(g, "payment_stripe_enabled", False)
                ),
                "payment_mock_enabled": bool(getattr(g, "payment_mock_enabled", False)),
                "payment_mode": str(getattr(g, "payment_mode", "") or ""),
            },
            "credential_refs": [
                "env:PAYMENT_STRIPE_SECRET_KEY",
                "env:PAYMENT_STRIPE_WEBHOOK_SECRET",
                "env:PAYMENT_MOCK_WEBHOOK_SECRET",
            ],
            "health_probes": {"configuration_probe": pay_st},
            "health_status": pay_st,
            "health_error_public": pay_err,
        }
    )
    upsert.append(
        {
            "integration_key": "payment_provider",
            "health_status": pay_st,
            "error_public": pay_err,
            "probe_detail": pay_detail,
        }
    )

    # --- LLM / AI ---
    llm = by_name.get("llm-orchestrator")
    llm_st = _svc_status(llm)
    llm_err = _svc_error_public(llm) if llm_st != "ok" else None
    fake = bool(getattr(g, "llm_use_fake_provider", False))
    if fake and llm_st == "ok":
        llm_st = "degraded"
        llm_err = "LLM_USE_FAKE_PROVIDER=true (kein Produktiv-Provider)"
    api_rows.append(
        {
            "integration_key": "llm_ai",
            "display_name_de": "LLM / KI-Orchestrierung",
            "display_name_en": "LLM / AI orchestration",
            "feature_flags": {
                "llm_use_fake_provider": fake,
            },
            "credential_refs": [
                "env:OPENAI_API_KEY",
                "env:ANTHROPIC_API_KEY",
                "service:llm-orchestrator secrets",
            ],
            "health_probes": {"llm_orchestrator": _svc_status(llm)},
            "health_status": llm_st,
            "health_error_public": llm_err,
        }
    )
    upsert.append(
        {
            "integration_key": "llm_ai",
            "health_status": llm_st,
            "error_public": llm_err,
            "probe_detail": {
                "llm_orchestrator": _svc_status(llm),
                "fake_provider": fake,
            },
        }
    )

    # --- Monitoring ---
    mon = by_name.get("monitor-engine")
    mon_st = _svc_status(mon)
    mon_err = _svc_error_public(mon) if mon_st != "ok" else None
    if mon_st == "ok" and open_alerts > 0:
        mon_st = "degraded"
        mon_err = f"open_monitor_alerts={open_alerts}"
    api_rows.append(
        {
            "integration_key": "monitoring",
            "display_name_de": "Monitoring (Monitor-Engine / Alerts)",
            "display_name_en": "Monitoring (monitor-engine / alerts)",
            "feature_flags": {},
            "credential_refs": [],
            "health_probes": {"monitor_engine": _svc_status(mon)},
            "health_status": mon_st,
            "health_error_public": mon_err,
            "ops_hint": {"open_alert_count": open_alerts},
        }
    )
    upsert.append(
        {
            "integration_key": "monitoring",
            "health_status": mon_st,
            "error_public": mon_err,
            "probe_detail": {
                "monitor_engine": _svc_status(mon),
                "open_alerts": open_alerts,
            },
        }
    )

    # --- Dashboard / Gateway ---
    gw_db = database_status
    redis_st = redis_status or "skipped"
    dg_st = _worst_status(
        "ok" if gw_db == "ok" else "error",
        "ok" if redis_st == "ok" else ("error" if redis_st == "error" else "ok"),
    )
    dg_err = None
    if gw_db != "ok":
        dg_err = "Datenbank nicht erreichbar"
    elif redis_st == "error":
        dg_err = "Redis nicht erreichbar"
    api_rows.append(
        {
            "integration_key": "dashboard_gateway",
            "display_name_de": "Dashboard / API-Gateway",
            "display_name_en": "Dashboard / API gateway",
            "feature_flags": {
                "sensitive_auth_enforced": g.sensitive_auth_enforced(),
                "gateway_auth_configured": g.gateway_auth_credentials_configured(),
                "commercial_enabled": bool(getattr(g, "commercial_enabled", False)),
            },
            "credential_refs": [
                "env:GATEWAY_JWT_SECRET",
                "env:GATEWAY_INTERNAL_API_KEY",
                "env:DASHBOARD_GATEWAY_AUTHORIZATION",
            ],
            "health_probes": {
                "database": gw_db,
                "redis": redis_st,
                "api_gateway": "ok",
            },
            "health_status": dg_st,
            "health_error_public": dg_err,
        }
    )
    upsert.append(
        {
            "integration_key": "dashboard_gateway",
            "health_status": dg_st,
            "error_public": dg_err,
            "probe_detail": {
                "database": gw_db,
                "redis": redis_st,
            },
        }
    )

    return api_rows, upsert


def merge_persisted_integration_fields(
    api_rows: list[dict[str, Any]],
    persisted: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reichert API-Zeilen mit DB-Zeitstempeln an (Tests / Legacy ohne Rollforward)."""
    out: list[dict[str, Any]] = []
    for row in api_rows:
        key = str(row["integration_key"])
        p = persisted.get(key) or {}
        r = dict(row)
        r["last_success_ts"] = _iso_utc(p.get("last_success_ts"))
        r["last_failure_ts"] = _iso_utc(p.get("last_failure_ts"))
        r["last_error_persisted"] = p.get("last_error_public")
        r["state_updated_ts"] = _iso_utc(p.get("updated_ts"))
        out.append(r)
    return out


def _iso_utc(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()
    return str(dt)


def roll_integration_connectivity_state(
    prev: dict[str, Any] | None,
    *,
    new_status: str,
    new_error_public: str | None,
    server_now: datetime,
) -> dict[str, Any]:
    """Aktualisiert rollierende Erfolgs-/Fehler-Zeitstempel."""
    prev = prev or {}
    ls = prev.get("last_success_ts")
    lf = prev.get("last_failure_ts")
    lep = prev.get("last_error_public")
    okish = new_status in ("ok", "disabled")
    badish = new_status in ("error", "misconfigured", "degraded", "not_configured")
    if okish:
        ls = server_now
        lep = None
    elif badish:
        lf = server_now
        if new_error_public:
            lep = str(new_error_public)[:2000]
    return {
        "last_success_ts": ls,
        "last_failure_ts": lf,
        "last_error_public": lep,
        "last_status": new_status[:64],
    }


def finalize_integrations_matrix_for_health(
    api_rows: list[dict[str, Any]],
    upsert_batch: list[dict[str, Any]],
    persisted_by_key: dict[str, dict[str, Any]],
    *,
    g: Any,
    server_now: datetime,
    server_ts_ms: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Erzeugt API-Block inkl. Rollforward und DB-Zeilen fuer Upsert."""
    merged_api: list[dict[str, Any]] = []
    db_rows: list[dict[str, Any]] = []
    by_upsert = {str(u["integration_key"]): u for u in upsert_batch}
    for row in api_rows:
        key = str(row["integration_key"])
        u = by_upsert[key]
        prev = persisted_by_key.get(key)
        rolled = roll_integration_connectivity_state(
            prev,
            new_status=str(u["health_status"]),
            new_error_public=u.get("error_public"),
            server_now=server_now,
        )
        detail = u.get("probe_detail") or {}
        if not isinstance(detail, dict):
            detail = {}
        merged = dict(row)
        merged["last_success_ts"] = _iso_utc(rolled["last_success_ts"])
        merged["last_failure_ts"] = _iso_utc(rolled["last_failure_ts"])
        merged["last_error_persisted"] = rolled["last_error_public"]
        merged["state_updated_ts"] = server_now.isoformat()
        merged["last_probe_ts"] = server_now.isoformat()
        merged_api.append(merged)
        db_rows.append(
            {
                "integration_key": key,
                "last_status": rolled["last_status"],
                "last_error_public": rolled["last_error_public"],
                "last_success_ts": rolled["last_success_ts"],
                "last_failure_ts": rolled["last_failure_ts"],
                "probe_detail_json": detail,
                "updated_ts": server_now,
            }
        )
    vm = str(getattr(g, "vault_mode", "false") or "false")
    wrapper: dict[str, Any] = {
        "schema_version": "integrations-matrix-v1",
        "server_ts_ms": server_ts_ms,
        "credential_policy": {
            "vault_mode": vm,
            "reference_only": True,
            "note_de": (
                "Sensible Werte erscheinen nur als Referenzen "
                "(ENV-Namen, Vault-Hinweise). Klartext-Secrets werden nicht "
                "geloggt oder in dieser Matrix ausgegeben."
            ),
            "note_en": (
                "Sensitive values appear only as references "
                "(env names, vault hints). Plaintext secrets are not logged "
                "or returned in this matrix."
            ),
        },
        "integrations": merged_api,
    }
    return wrapper, db_rows
