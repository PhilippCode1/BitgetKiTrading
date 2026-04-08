import {
  buildSafetyDiagnosticContext,
  redactSensitiveDiagnosticBranches,
} from "@/lib/safety-diagnosis-context";
import type {
  AlertOutboxItem,
  MonitorAlertItem,
  SystemHealthResponse,
} from "@/lib/types";

describe("safety-diagnosis-context", () => {
  it("redacts sensitive keys", () => {
    const out = redactSensitiveDiagnosticBranches({
      ok: true,
      api_key: "secret",
      nested: { user_password: "x" },
    }) as Record<string, unknown>;
    expect(out.api_key).toBe("[REMOVED]");
    expect((out.nested as Record<string, unknown>).user_password).toBe(
      "[REMOVED]",
    );
  });

  it("builds bundle with alerts and health slice", () => {
    const health = {
      server_ts_ms: 1,
      symbol: "BTCUSDT",
      execution: {
        execution_mode: "paper",
        strategy_execution_mode: "auto",
        paper_path_active: true,
        shadow_trade_enable: false,
        shadow_path_active: false,
        live_trade_enable: false,
        live_order_submission_enabled: false,
      },
      database: "ok",
      data_freshness: {
        last_candle_ts_ms: null,
        last_signal_ts_ms: null,
        last_news_ts_ms: null,
      },
      stream_lengths_top: [],
      services: [{ name: "gateway", status: "ok", configured: true }],
      ops: {
        monitor: { open_alert_count: 0 },
        alert_engine: {
          outbox_pending: 0,
          outbox_failed: 0,
          outbox_sending: 0,
        },
        live_broker: {
          latest_reconcile_status: null,
          latest_reconcile_created_ts: null,
          latest_reconcile_age_ms: null,
          latest_reconcile_drift_total: 0,
          active_kill_switch_count: 0,
          last_fill_created_ts: null,
          last_fill_age_ms: null,
          critical_audit_count_24h: 0,
          order_status_counts: {},
        },
      },
      warnings: [],
    } as unknown as SystemHealthResponse;

    const alerts: MonitorAlertItem[] = [
      {
        alert_key: "k1",
        severity: "warn",
        title: "T",
        message: "M",
        details: { token: "bad" },
        state: "open",
        created_ts: null,
        updated_ts: null,
      },
    ];

    const outbox: AlertOutboxItem[] = [];

    const ctx = buildSafetyDiagnosticContext({
      health,
      openAlerts: alerts,
      outbox,
      loadError: null,
    });
    expect(ctx.context_kind).toBe("safety_diagnostic_v1");
    expect(Array.isArray(ctx.monitor_open_alerts)).toBe(true);
    const first = (
      ctx.monitor_open_alerts as { details: { token: unknown } }[]
    )[0];
    expect(first.details.token).toBe("[REMOVED]");
  });
});
