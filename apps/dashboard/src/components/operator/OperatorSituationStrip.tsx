import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import type { OperatorSituationSummary } from "@/lib/operator-snapshot";

type Props = Readonly<{
  summary: OperatorSituationSummary;
  symbol: string;
  timeframe: string;
}>;

function driftClass(action: string | null): string {
  const a = (action || "").toLowerCase();
  if (a === "hard_block") return "operator-strip-item operator-strip-critical";
  if (a === "shadow_only") return "operator-strip-item operator-strip-warn";
  if (a === "warn") return "operator-strip-item operator-strip-warn";
  return "operator-strip-item";
}

export function OperatorSituationStrip({ summary, symbol, timeframe }: Props) {
  const killHot = summary.killSwitchActiveCount > 0;
  const latchHot = summary.safetyLatchActive;
  const alertsHot = summary.openMonitorAlerts > 0;
  const brokerDegraded =
    summary.brokerServiceStatus && summary.brokerServiceStatus !== "ok";

  return (
    <section
      className="operator-situation-strip"
      aria-label="Operator-Lage kompakt"
      role="region"
    >
      <div className="operator-strip-grid">
        <div className="operator-strip-item">
          <span className="operator-strip-k">Modus</span>
          <span className="operator-strip-v">
            <strong>{summary.executionMode}</strong> / {summary.strategyMode}
          </span>
        </div>
        <div
          className={
            summary.liveSubmissionEnabled
              ? "operator-strip-item operator-strip-live"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">Live</span>
          <span className="operator-strip-v">
            trade <strong>{String(summary.liveTradeEnable)}</strong> — submit{" "}
            <strong>{String(summary.liveSubmissionEnabled)}</strong>
          </span>
        </div>
        <div
          className={
            killHot
              ? "operator-strip-item operator-strip-critical"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">Kill-Switch</span>
          <span className="operator-strip-v">
            <strong>{summary.killSwitchActiveCount}</strong> aktiv
          </span>
        </div>
        <div
          className={
            latchHot
              ? "operator-strip-item operator-strip-critical"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">Safety-Latch</span>
          <span className="operator-strip-v">
            <strong>{latchHot ? "AN" : "aus"}</strong>
          </span>
        </div>
        <div className={driftClass(summary.onlineDriftAction)}>
          <span className="operator-strip-k">Online-Drift</span>
          <span className="operator-strip-v">
            <strong>{summary.onlineDriftAction ?? "—"}</strong>
            {summary.onlineDriftComputedAt ? (
              <span className="muted"> @ {summary.onlineDriftComputedAt}</span>
            ) : null}
          </span>
        </div>
        <div
          className={
            alertsHot
              ? "operator-strip-item operator-strip-warn"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">Monitor-Alerts</span>
          <span className="operator-strip-v">
            <strong>{summary.openMonitorAlerts}</strong> offen
          </span>
        </div>
        <div
          className={
            brokerDegraded
              ? "operator-strip-item operator-strip-warn"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">Broker-Probe</span>
          <span className="operator-strip-v">
            {summary.brokerServiceName ? (
              <>
                <code>{summary.brokerServiceName}</code>{" "}
                <strong>{summary.brokerServiceStatus ?? "—"}</strong>
              </>
            ) : (
              <span className="muted">—</span>
            )}
          </span>
        </div>
        <div className="operator-strip-item">
          <span className="operator-strip-k">Reconcile</span>
          <span className="operator-strip-v">
            {summary.reconcileStatus ?? "—"}
          </span>
        </div>
        <div
          className={
            summary.databaseOk
              ? "operator-strip-item"
              : "operator-strip-item operator-strip-warn"
          }
        >
          <span className="operator-strip-k">DB</span>
          <span className="operator-strip-v">
            <strong>{summary.databaseOk ? "ok" : "Fehler"}</strong>
          </span>
        </div>
        <div className="operator-strip-item">
          <span className="operator-strip-k">Drift-Events (Fenster)</span>
          <span className="operator-strip-v">
            <strong>{summary.recentDriftEventCount}</strong>{" "}
            <Link
              href={consolePath("learning")}
              className="operator-strip-link"
            >
              Learning
            </Link>
          </span>
        </div>
      </div>
      <p className="muted operator-strip-foot">
        Kontext: <code>{symbol}</code> / <code>{timeframe}</code> —
        Vollstaendige Schalter:{" "}
        <Link href={consolePath("health")}>System-Health</Link>, Live-Journal:{" "}
        <Link href={consolePath("live-broker")}>Live-Broker</Link>, Signale:{" "}
        <Link href={consolePath("signals")}>Signal-Center</Link>.
      </p>
    </section>
  );
}
