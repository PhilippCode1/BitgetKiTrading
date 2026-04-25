import type { SystemHealthResponse } from "@/lib/types";
import type { ExecutionTierSnapshot } from "@/lib/types";

type Props = Readonly<{
  health: SystemHealthResponse | null;
  tier: ExecutionTierSnapshot | null;
  healthError: boolean;
}>;

function modeLabel(tier: ExecutionTierSnapshot | null): string {
  if (!tier) return "Live blockiert";
  if ((tier.execution_mode || "").toLowerCase() === "bitget_demo") return "Bitget Demo";
  if (tier.trading_plane === "live") {
    return tier.live_order_submission_enabled ? "Live bereit" : "Live blockiert";
  }
  if ((tier.deployment || "").toLowerCase().includes("staging")) return "Staging";
  if ((tier.deployment || "").toLowerCase().includes("local")) return "Local";
  if (tier.trading_plane === "shadow") return "Shadow";
  return "Paper";
}

function safetyLabel(health: SystemHealthResponse | null, healthError: boolean): string {
  if (healthError || !health) return "Blockiert";
  if (health.aggregate?.level === "red") return "Blockiert";
  if (health.aggregate?.level === "degraded") return "Warnung";
  return "OK";
}

function bitgetLabel(health: SystemHealthResponse | null, healthError: boolean): string {
  if (healthError || !health) return "Unbekannt";
  const hasBitgetProbe = health.services.some(
    (svc) =>
      Boolean(svc.bitget_ws_stream) ||
      Boolean(svc.private_ws) ||
      svc.name.toLowerCase().includes("bitget"),
  );
  if (!hasBitgetProbe) return "Unbekannt";
  const degraded = health.services.some(
    (svc) =>
      (svc.name.toLowerCase().includes("market-stream") ||
        svc.name.toLowerCase().includes("live-broker") ||
        svc.name.toLowerCase().includes("bitget")) &&
      (svc.status || "").toLowerCase() !== "ok",
  );
  return degraded ? "Warnung" : "OK";
}

function dataQualityLabel(health: SystemHealthResponse | null, healthError: boolean): string {
  if (healthError || !health) return "Unbekannt";
  const hasCoreData =
    health.data_freshness.last_candle_ts_ms != null &&
    health.data_freshness.last_signal_ts_ms != null;
  if (!hasCoreData) return "Warnung";
  return (health.warnings || []).length > 0 ? "Warnung" : "OK";
}

function brokerReconcileLabel(
  health: SystemHealthResponse | null,
  healthError: boolean,
): string {
  if (healthError || !health) return "Unbekannt";
  const broker = health.services.find((svc) =>
    svc.name.toLowerCase().includes("live-broker"),
  );
  const brokerState = (broker?.status || "unknown").toLowerCase();
  const reconcile = (health.ops.live_broker.latest_reconcile_status || "unknown").toLowerCase();
  if (brokerState !== "ok" || reconcile.includes("drift") || reconcile.includes("fail")) {
    return "Warnung";
  }
  return reconcile === "unknown" ? "Unbekannt" : "OK";
}

export function MainConsoleStatusBar({ health, tier, healthError }: Props) {
  return (
    <section className="main-console-statusbar" aria-label="Globaler Main-Console-Status">
      <div className="main-console-statusbar__project">
        <strong>bitget-btc-ai</strong>
      </div>
      <div className="main-console-statusbar__badges">
        <span className="main-console-statusbar__badge">
          Betriebsmodus: <strong>{modeLabel(tier)}</strong>
        </span>
        <span className="main-console-statusbar__badge">
          Sicherheit: <strong>{safetyLabel(health, healthError)}</strong>
        </span>
        <span className="main-console-statusbar__badge">
          Bitget: <strong>{bitgetLabel(health, healthError)}</strong>
        </span>
        <span className="main-console-statusbar__badge">
          Datenqualität: <strong>{dataQualityLabel(health, healthError)}</strong>
        </span>
        <span className="main-console-statusbar__badge">
          Broker/Reconcile: <strong>{brokerReconcileLabel(health, healthError)}</strong>
        </span>
      </div>
    </section>
  );
}
