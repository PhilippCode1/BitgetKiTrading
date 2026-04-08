import Link from "next/link";

import {
  formatServiceStatus,
  serviceByName,
  summarizeWsTelemetry,
} from "@/lib/market-universe-lineage";
import { consolePath } from "@/lib/console-paths";
import { getRequestLocale } from "@/lib/i18n/server";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { SystemHealthResponse } from "@/lib/types";

type Props = Readonly<{
  health: SystemHealthResponse | null;
  /** `card`: eigenes Panel (Terminal/Signale). `bare`: nur Raster (eingebettet Marktuniversum). */
  variant?: "card" | "bare";
  /** E2E — bei `bare` optional weglassen (Parent hat testid). */
  testId?: string;
}>;

function fmtTsMs(ts: number | null | undefined, locale: string): string {
  if (ts == null || !Number.isFinite(ts)) return "—";
  return new Date(ts).toLocaleString(locale);
}

/**
 * Plattform-Sicht aus System-Health: Spuren, Kerzen-/Signal-Zeit, market-stream,
 * live-broker, Reconcile — wiederverwendbar auf Terminal, Signale, Marktuniversum.
 */
export async function PlatformExecutionStreamsGrid({
  health,
  variant = "card",
  testId = "platform-execution-lineage",
}: Props) {
  const t = await getServerTranslator();
  const reqLocale = await getRequestLocale();
  const locale = reqLocale === "en" ? "en-US" : "de-DE";

  const execMode = health?.execution.execution_mode ?? "—";
  const stratMode = health?.execution.strategy_execution_mode ?? "—";
  const lanePaper = health?.execution.paper_path_active === true;
  const laneShadow =
    health?.execution.shadow_path_active === true ||
    health?.execution.shadow_trade_enable === true;
  const laneLive = health?.execution.live_trade_enable === true;

  const ms = serviceByName(health?.services, "market-stream");
  const lb = serviceByName(health?.services, "live-broker");
  const wsPub = ms?.bitget_ws_stream as Record<string, unknown> | undefined;
  const wsPriv = lb?.private_ws as Record<string, unknown> | undefined;
  const ops = health?.ops?.live_broker;

  const grid = (
    <div className="signal-grid market-universe-lineage__grid">
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageExecMode")}
        </span>
        <div>{execMode}</div>
        <div className="mono-small muted">
          {t("pages.marketUniverse.lineageStrategyMode")}: {stratMode}
        </div>
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageLanes")}
        </span>
        <div className="market-universe-lineage__lanes">
          <span
            className={
              laneLive
                ? "market-universe-lineage__pill market-universe-lineage__pill--on"
                : "market-universe-lineage__pill"
            }
          >
            LIVE
          </span>
          <span
            className={
              laneShadow
                ? "market-universe-lineage__pill market-universe-lineage__pill--on"
                : "market-universe-lineage__pill"
            }
          >
            SHADOW
          </span>
          <span
            className={
              lanePaper
                ? "market-universe-lineage__pill market-universe-lineage__pill--on"
                : "market-universe-lineage__pill"
            }
          >
            PAPER
          </span>
        </div>
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageLastCandle")}
        </span>
        <div>{fmtTsMs(health?.data_freshness.last_candle_ts_ms, locale)}</div>
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageLastSignal")}
        </span>
        <div>{fmtTsMs(health?.data_freshness.last_signal_ts_ms, locale)}</div>
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageMarketStream")}
        </span>
        <div>
          {ms
            ? formatServiceStatus(ms)
            : t("pages.marketUniverse.lineageNoHealth")}
        </div>
        {wsPub && Object.keys(wsPub).length > 0 ? (
          <div className="mono-small muted">
            {summarizeWsTelemetry(wsPub) || "—"}
          </div>
        ) : (
          <div className="mono-small muted">
            {t("pages.marketUniverse.lineageWsPublicMissing")}
          </div>
        )}
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageLiveBrokerSvc")}
        </span>
        <div>
          {lb
            ? formatServiceStatus(lb)
            : t("pages.marketUniverse.lineageNoHealth")}
        </div>
        {wsPriv && Object.keys(wsPriv).length > 0 ? (
          <div className="mono-small muted">
            {summarizeWsTelemetry(wsPriv) || "—"}
          </div>
        ) : null}
      </div>
      <div>
        <span className="label">
          {t("pages.marketUniverse.lineageReconcile")}
        </span>
        <div>
          {ops?.latest_reconcile_status ?? "—"}
          {ops?.latest_reconcile_created_ts
            ? ` · ${ops.latest_reconcile_created_ts}`
            : ""}
        </div>
        <div className="mono-small muted">
          {t("pages.marketUniverse.lineageReconcileDrift", {
            n: ops?.latest_reconcile_drift_total ?? 0,
          })}
        </div>
      </div>
    </div>
  );

  if (variant === "bare") {
    return grid;
  }

  return (
    <div
      className="panel platform-execution-streams"
      data-testid={testId}
      aria-label={t("live.platformLineage.gridAria")}
    >
      <h2 className="platform-execution-streams__title">
        {t("live.platformLineage.title")}
      </h2>
      <p className="muted small">{t("live.platformLineage.lead")}</p>
      {grid}
      <p className="muted small platform-execution-streams__footer">
        <Link href={consolePath("market-universe")}>
          {t("live.platformLineage.linkFullUniverse")}
        </Link>
        {" · "}
        <Link href={consolePath("self-healing")}>
          {t("console.nav.self_healing")}
        </Link>
        {" · "}
        <Link href={consolePath("diagnostics")}>
          {t("console.nav.diagnostics")}
        </Link>
        {" · "}
        <Link href={consolePath("live-broker")}>
          {t("console.nav.live_broker")}
        </Link>
      </p>
    </div>
  );
}
