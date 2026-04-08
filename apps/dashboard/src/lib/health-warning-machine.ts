import type { HealthWarningMachine, SystemHealthResponse } from "@/lib/types";

function opsSignals(health: SystemHealthResponse): Record<string, unknown> {
  const ops = health.ops;
  const mon = ops?.monitor as { open_alert_count?: number } | undefined;
  const ae = ops?.alert_engine as
    | {
        outbox_failed?: number;
        outbox_pending?: number;
      }
    | undefined;
  const lb = ops?.live_broker as
    | {
        latest_reconcile_status?: string | null;
        active_kill_switch_count?: number;
        safety_latch_active?: boolean;
        critical_audit_count_24h?: number;
      }
    | undefined;
  return {
    open_alert_count: Number(mon?.open_alert_count ?? 0),
    outbox_failed: Number(ae?.outbox_failed ?? 0),
    outbox_pending: Number(ae?.outbox_pending ?? 0),
    latest_reconcile_status: lb?.latest_reconcile_status ?? null,
    active_kill_switch_count: Number(lb?.active_kill_switch_count ?? 0),
    safety_latch_active: Boolean(lb?.safety_latch_active),
    critical_audit_count_24h: Number(lb?.critical_audit_count_24h ?? 0),
  };
}

export function buildMachineRemediation(
  code: string,
  health: SystemHealthResponse,
): HealthWarningMachine {
  const c = (code || "").trim();
  const sig = opsSignals(health);
  const facts: Record<string, unknown> = { warning_code: c, ...sig };

  const base = (
    problem_id: string,
    severity: string,
    summary_en: string,
    actions: Array<Record<string, unknown>>,
    verify: string[],
    extraFacts?: Record<string, unknown>,
  ): HealthWarningMachine => ({
    schema_version: "health-warning-machine-v1",
    problem_id,
    severity,
    summary_en,
    facts: extraFacts ? { ...facts, ...extraFacts } : facts,
    suggested_actions: actions,
    verify_commands: verify,
  });

  if (c === "monitor_alerts_open") {
    const n = Number(sig.open_alert_count ?? 0);
    return base(
      "health.ops_alerts_open",
      "warn",
      `Postgres ops.alerts has ${n} rows with state=open. Health adds warning when count>0. ` +
        "Resolve root causes then set resolved/acked, or set LIVE_REQUIRE_EXCHANGE_HEALTH=false locally if Bitget probe noise without API keys.",
      [
        {
          type: "http_inspect",
          method: "GET",
          path: "/v1/monitor/alerts/open",
        },
        {
          type: "env_optional",
          key: "LIVE_REQUIRE_EXCHANGE_HEALTH",
          value: "false",
          when_en: "local/paper without Bitget credentials",
        },
        {
          type: "sql_reference",
          path: "scripts/sql/close_open_monitor_alerts_local.sql",
        },
        {
          type: "sql_reference",
          path: "scripts/sql/close_open_monitor_alerts_local_all.sql",
        },
        {
          type: "dev_script",
          command: "pnpm alerts:close-local-all",
          purpose_en:
            "PowerShell helper at repo root; closes open ops.alerts after review",
        },
        {
          type: "compose_logs",
          services: ["monitor-engine", "live-broker", "api-gateway"],
        },
      ],
      [
        "docker compose ps monitor-engine live-broker api-gateway",
        'curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".warnings,.ops.monitor,.warnings_display"',
      ],
    );
  }

  if (c === "alert_outbox_failed") {
    const f = Number(sig.outbox_failed ?? 0);
    return base(
      "health.alert_outbox_failed",
      "warn",
      `alert.alert_outbox has ${f} failed rows; fix Telegram bot, tokens, or network.`,
      [
        {
          type: "http_inspect",
          method: "GET",
          path: "/v1/alerts/outbox/recent",
        },
        { type: "compose_logs", services: ["alert-engine"] },
      ],
      ['curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".ops.alert_engine"'],
    );
  }

  if (c === "no_candles_timestamp" || c === "stale_candles") {
    return base(
      `health.${c}`,
      c === "stale_candles" ? "warn" : "info",
      "Candle freshness missing or older than DATA_STALE_WARN_MS for health symbol.",
      [
        { type: "compose_logs", services: ["market-stream", "feature-engine"] },
        {
          type: "env_check",
          keys: ["BITGET_UNIVERSE_SYMBOLS", "DATA_STALE_WARN_MS"],
        },
      ],
      [
        'curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".data_freshness,.symbol"',
      ],
    );
  }

  if (c === "no_signals_timestamp" || c === "stale_signals") {
    return base(
      `health.${c}`,
      c === "stale_signals" ? "warn" : "info",
      "Signal freshness missing or stale for health symbol.",
      [
        {
          type: "compose_logs",
          services: ["signal-engine", "drawing-engine", "structure-engine"],
        },
      ],
      ['curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".data_freshness"'],
    );
  }

  if (c === "no_news_timestamp" || c === "stale_news") {
    return base(
      `health.${c}`,
      c === "stale_news" ? "warn" : "info",
      "News freshness (global) missing or stale.",
      [{ type: "compose_logs", services: ["news-engine", "llm-orchestrator"] }],
      [],
    );
  }

  if (
    c === "live_broker_kill_switch_active" ||
    c === "live_broker_safety_latch_active" ||
    c === "live_broker_critical_audits_open"
  ) {
    return base(
      `health.${c}`,
      "critical",
      `Live broker safety/audit condition: ${c}.`,
      [
        { type: "http_inspect", path: "/v1/live-broker/runtime" },
        { type: "compose_logs", services: ["live-broker"] },
      ],
      ['curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".ops.live_broker"'],
    );
  }

  if (c.startsWith("live_broker_reconcile_")) {
    const st = c.slice("live_broker_reconcile_".length);
    return base(
      "health.live_broker_reconcile_not_ok",
      "warn",
      `Latest reconcile snapshot status not ok: ${JSON.stringify(st)}.`,
      [{ type: "compose_logs", services: ["live-broker"] }],
      ['curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".ops.live_broker"'],
      { reconcile_status: st },
    );
  }

  return base(
    c ? `health.unmapped.${c}` : "health.unmapped",
    "warn",
    "Unmapped health warning code; fetch full GET /v1/system/health and api-gateway logs.",
    [
      { type: "http_inspect", path: "/v1/system/health" },
      { type: "compose_logs", services: ["api-gateway"] },
    ],
    [
      'curl -sS "$API_GATEWAY_URL/v1/system/health" | jq ".warnings, .warnings_display, .services"',
    ],
    { raw_code: c },
  );
}
