import { formatIsoTs } from "@/lib/format";
import type { ExecutionPathViewModel } from "@/lib/execution-path-view-model";

type Translate = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

function boolLabel(v: boolean, t: Translate): string {
  return v ? t("ui.executionPath.valueYes") : t("ui.executionPath.valueNo");
}

/**
 * Einheitliche Darstellung von Paper/Shadow/Live — gleiche Labels wie Health/Paper/Cockpit.
 */
export function ExecutionPathSummaryList({
  model,
  t,
}: Readonly<{
  model: ExecutionPathViewModel | null;
  t: Translate;
}>) {
  if (!model) {
    return (
      <p className="muted small" role="status">
        {t("ui.executionPath.unavailable")}
      </p>
    );
  }

  return (
    <ul className="news-list console-execution-path-summary">
      {model.runtime_status != null && model.runtime_status.length > 0 ? (
        <li>
          {t("ui.executionPath.runtimeStatus")}:{" "}
          <strong>{model.runtime_status}</strong>
        </li>
      ) : null}
      {model.upstream_ok != null ? (
        <li>
          {t("ui.executionPath.upstreamOk")}:{" "}
          <strong>{boolLabel(model.upstream_ok, t)}</strong>
        </li>
      ) : null}
      {model.snapshot_ts != null && model.snapshot_ts.length > 0 ? (
        <li>
          {t("ui.executionPath.snapshotTs")}:{" "}
          <strong>{formatIsoTs(model.snapshot_ts)}</strong>
        </li>
      ) : null}
      <li>
        {t("ui.executionPath.executionMode")}:{" "}
        <strong>{model.execution_mode}</strong>
      </li>
      <li>
        {t("ui.executionPath.strategyMode")}:{" "}
        <strong>{model.strategy_execution_mode}</strong>
      </li>
      <li>
        {t("ui.executionPath.paperPath")}:{" "}
        <strong>{boolLabel(model.paper_path_active, t)}</strong>
      </li>
      <li>
        {t("ui.executionPath.shadowGate")}:{" "}
        <strong>{boolLabel(model.shadow_trade_enable, t)}</strong>
      </li>
      <li>
        {t("ui.executionPath.shadowPath")}:{" "}
        <strong>{boolLabel(model.shadow_path_active, t)}</strong>
      </li>
      <li>
        {t("ui.executionPath.liveGate")}:{" "}
        <strong>{boolLabel(model.live_trade_enable, t)}</strong>
      </li>
      <li>
        {t("ui.executionPath.liveSubmit")}:{" "}
        <strong>{boolLabel(model.live_order_submission_enabled, t)}</strong>
      </li>
      {model.source === "live_broker_runtime" ? (
        <li>
          {t("ui.executionPath.shadowMatch")}:{" "}
          <strong>
            {boolLabel(model.require_shadow_match_before_live, t)}
          </strong>
        </li>
      ) : null}
    </ul>
  );
}
