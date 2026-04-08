import type { LiveBrokerRuntimeItem, SystemHealthResponse } from "@/lib/types";

/**
 * Vereinheitlichte Sicht auf Paper/Shadow/Live-Pfade — unabhaengig von
 * {@link SystemHealthResponse.execution} vs. {@link LiveBrokerRuntimeItem}.
 */
export type ExecutionPathViewModel = Readonly<{
  source: "system_health" | "live_broker_runtime";
  execution_mode: string;
  strategy_execution_mode: string;
  paper_path_active: boolean;
  shadow_trade_enable: boolean;
  shadow_path_active: boolean;
  live_trade_enable: boolean;
  live_order_submission_enabled: boolean;
  require_shadow_match_before_live: boolean;
  /** Nur Live-Broker-Runtime */
  runtime_status?: string | null;
  upstream_ok?: boolean | null;
  /** Live-Broker Snapshot-Zeit (API-Rohstring, Anzeige mit formatIsoTs) */
  snapshot_ts?: string | null;
}>;

export function executionPathFromSystemHealth(
  health: SystemHealthResponse | null | undefined,
): ExecutionPathViewModel | null {
  if (!health?.execution) return null;
  const ex = health.execution;
  return {
    source: "system_health",
    execution_mode: ex.execution_mode,
    strategy_execution_mode: ex.strategy_execution_mode,
    paper_path_active: Boolean(ex.paper_path_active),
    shadow_trade_enable: Boolean(ex.shadow_trade_enable),
    shadow_path_active: Boolean(ex.shadow_path_active),
    live_trade_enable: Boolean(ex.live_trade_enable),
    live_order_submission_enabled: Boolean(ex.live_order_submission_enabled),
    require_shadow_match_before_live: false,
  };
}

export function executionPathFromLiveBrokerRuntime(
  item: LiveBrokerRuntimeItem | null | undefined,
): ExecutionPathViewModel | null {
  if (!item) return null;
  return {
    source: "live_broker_runtime",
    execution_mode: item.execution_mode,
    strategy_execution_mode: item.strategy_execution_mode?.trim() || "—",
    paper_path_active: Boolean(item.paper_path_active),
    shadow_trade_enable: Boolean(item.shadow_trade_enable),
    shadow_path_active: Boolean(item.shadow_path_active),
    live_trade_enable: Boolean(item.live_trade_enable),
    live_order_submission_enabled: Boolean(item.live_order_submission_enabled),
    require_shadow_match_before_live: Boolean(
      item.require_shadow_match_before_live,
    ),
    runtime_status: item.status ?? null,
    upstream_ok: item.upstream_ok,
    snapshot_ts: item.created_ts ?? null,
  };
}
