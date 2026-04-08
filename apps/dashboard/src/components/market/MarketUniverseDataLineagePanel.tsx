import Link from "next/link";

import {
  buildCoreSymbolRows,
  formatServiceStatus,
  MARKET_UNIVERSE_CORE_SYMBOLS,
  serviceByName,
  summarizeWsTelemetry,
} from "@/lib/market-universe-lineage";
import { consolePath } from "@/lib/console-paths";
import { getRequestLocale } from "@/lib/i18n/server";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type {
  MarketUniverseInstrumentItem,
  SystemHealthResponse,
} from "@/lib/types";

type Props = Readonly<{
  health: SystemHealthResponse | null;
  instruments: readonly MarketUniverseInstrumentItem[];
}>;

function fmtTsMs(ts: number | null | undefined, locale: string): string {
  if (ts == null || !Number.isFinite(ts)) return "—";
  return new Date(ts).toLocaleString(locale);
}

/**
 * Sprint 2: LIVE/SHADOW/PAPER und technische Datenpfade sichtbar —
 * Market-Stream-Telemetrie, Broker-Reconcile, Kerzen/SIGNAL-Zeit, Kernsymbole.
 */
export async function MarketUniverseDataLineagePanel({
  health,
  instruments,
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
  const coreRows = buildCoreSymbolRows(
    instruments,
    MARKET_UNIVERSE_CORE_SYMBOLS,
  );

  return (
    <section
      className="panel market-universe-lineage"
      data-testid="market-universe-lineage"
      aria-label={t("pages.marketUniverse.lineageTitle")}
    >
      <h2>{t("pages.marketUniverse.lineageTitle")}</h2>
      <p className="muted small">{t("pages.marketUniverse.lineageLead")}</p>

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

      <h3 className="market-universe-lineage__sub">
        {t("pages.marketUniverse.lineageCoreSymbols")}
      </h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("pages.marketUniverse.lineageThSymbol")}</th>
              <th>{t("pages.marketUniverse.lineageThRegistry")}</th>
              <th>{t("pages.marketUniverse.lineageThLive")}</th>
              <th>{t("pages.marketUniverse.lineageThSubscribe")}</th>
              <th>{t("pages.marketUniverse.lineageThTrade")}</th>
              <th>{t("pages.marketUniverse.lineageThStatus")}</th>
              <th>{t("pages.marketUniverse.lineageThChart")}</th>
            </tr>
          </thead>
          <tbody>
            {coreRows.map((row) => (
              <tr key={row.symbol}>
                <td className="mono-small">{row.symbol}</td>
                <td>{row.inRegistry ? t("account.yes") : t("account.no")}</td>
                <td>
                  {row.inRegistry
                    ? row.liveEnabled
                      ? t("account.yes")
                      : t("account.no")
                    : "—"}
                </td>
                <td>
                  {row.inRegistry
                    ? row.subscribeEnabled
                      ? t("account.yes")
                      : t("account.no")
                    : "—"}
                </td>
                <td>
                  {row.inRegistry
                    ? row.tradingEnabled
                      ? t("account.yes")
                      : t("account.no")
                    : "—"}
                </td>
                <td>{row.inRegistry ? row.tradingStatus : "—"}</td>
                <td>
                  <Link
                    href={`${consolePath("market-universe")}?${new URLSearchParams({ symbol: row.symbol }).toString()}`}
                  >
                    {t("pages.marketUniverse.lineageOpenChart")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted small market-universe-lineage__footer">
        {t("pages.marketUniverse.lineageSelfHealHint")}{" "}
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
    </section>
  );
}
