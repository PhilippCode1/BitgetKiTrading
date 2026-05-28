"use client";

import Link from "next/link";

import { useI18n } from "@/components/i18n/I18nProvider";
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
  const { t } = useI18n();
  const killHot = summary.killSwitchActiveCount > 0;
  const latchHot = summary.safetyLatchActive;
  const alertsHot = summary.openMonitorAlerts > 0;
  const brokerDegraded =
    summary.brokerServiceStatus && summary.brokerServiceStatus !== "ok";

  return (
    <section
      className="operator-situation-strip"
      aria-label={t("console.operatorStrip.ariaLabel")}
      role="region"
    >
      <div className="operator-strip-grid">
        <div className="operator-strip-item">
          <span className="operator-strip-k">{t("console.operatorStrip.mode")}</span>
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
          <span className="operator-strip-k">{t("console.operatorStrip.live")}</span>
          <span className="operator-strip-v">
            {t("console.operatorStrip.liveTrade")}{" "}
            <strong>{String(summary.liveTradeEnable)}</strong> —{" "}
            {t("console.operatorStrip.liveSubmit")}{" "}
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
          <span className="operator-strip-k">
            {t("console.operatorStrip.killSwitch")}
          </span>
          <span className="operator-strip-v">
            <strong>{summary.killSwitchActiveCount}</strong>{" "}
            {t("console.operatorStrip.killActive")}
          </span>
        </div>
        <div
          className={
            latchHot
              ? "operator-strip-item operator-strip-critical"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">
            {t("console.operatorStrip.safetyLatch")}
          </span>
          <span className="operator-strip-v">
            <strong>
              {latchHot
                ? t("console.operatorStrip.latchOn")
                : t("console.operatorStrip.latchOff")}
            </strong>
          </span>
        </div>
        <div className={driftClass(summary.onlineDriftAction)}>
          <span className="operator-strip-k">
            {t("console.operatorStrip.onlineDrift")}
          </span>
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
          <span className="operator-strip-k">
            {t("console.operatorStrip.monitorAlerts")}
          </span>
          <span className="operator-strip-v">
            <strong>{summary.openMonitorAlerts}</strong>{" "}
            {t("console.operatorStrip.monitorOpen")}
          </span>
        </div>
        <div
          className={
            brokerDegraded
              ? "operator-strip-item operator-strip-warn"
              : "operator-strip-item"
          }
        >
          <span className="operator-strip-k">
            {t("console.operatorStrip.brokerProbe")}
          </span>
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
          <span className="operator-strip-k">
            {t("console.operatorStrip.reconcile")}
          </span>
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
          <span className="operator-strip-k">{t("console.operatorStrip.db")}</span>
          <span className="operator-strip-v">
            <strong>
              {summary.databaseOk ? "ok" : t("console.operatorStrip.dbError")}
            </strong>
          </span>
        </div>
        <div className="operator-strip-item">
          <span className="operator-strip-k">
            {t("console.operatorStrip.driftEvents")}
          </span>
          <span className="operator-strip-v">
            <strong>{summary.recentDriftEventCount}</strong>{" "}
            <Link
              href={consolePath("learning")}
              className="operator-strip-link"
            >
              {t("console.operatorStrip.learningLink")}
            </Link>
          </span>
        </div>
      </div>
      <p className="muted operator-strip-foot">
        {t("console.operatorStrip.footerContext")}{" "}
        <code>{symbol}</code> / <code>{timeframe}</code> —{" "}
        {t("console.operatorStrip.footerFullSwitches")}{" "}
        <Link href={consolePath("health")}>
          {t("console.operatorStrip.footerHealth")}
        </Link>
        , {t("console.operatorStrip.footerLiveBroker")}:{" "}
        <Link href={consolePath("live-broker")}>
          {t("console.operatorStrip.footerLiveBroker")}
        </Link>
        , {t("console.operatorStrip.footerSignals")}:{" "}
        <Link href={consolePath("signals")}>
          {t("console.operatorStrip.footerSignals")}
        </Link>
        .
      </p>
    </section>
  );
}
