import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import {
  fetchLiveBrokerDecisions,
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerOrders,
  fetchLiveBrokerRuntime,
  fetchLiveState,
  fetchMarketUniverseStatus,
  fetchSignalsRecent,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import {
  buildAssetRiskRows,
  computeLiveBlockers,
  computeOverallStatus,
  computeRiskOverviewFromRuntime,
  portfolioRiskSummary,
} from "@/lib/risk-center-view-model";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

function first(sp: SP, key: string): string | undefined {
  const value = sp[key];
  return Array.isArray(value) ? value[0] : value;
}

export default async function RiskCenterPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const sp = await Promise.resolve(searchParams);
  const t = await getServerTranslator();
  const symbol = first(sp, "symbol")?.trim() || "BTCUSDT";
  const timeframe = first(sp, "timeframe")?.trim() || "5m";

  const settled = await Promise.allSettled([
    fetchSystemHealthBestEffort(),
    fetchLiveState({ symbol, timeframe, limit: 120 }),
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchLiveBrokerDecisions(),
    fetchLiveBrokerOrders(),
    fetchMarketUniverseStatus(),
    fetchSignalsRecent({ limit: 60 }),
  ]);

  const healthPack =
    settled[0].status === "fulfilled"
      ? settled[0].value
      : { health: null, error: new Error("health failed") };
  const live = settled[1].status === "fulfilled" ? settled[1].value : null;
  const runtime = settled[2].status === "fulfilled" ? settled[2].value.item : null;
  const killSwitches = settled[3].status === "fulfilled" ? settled[3].value.items : [];
  const decisions = settled[4].status === "fulfilled" ? settled[4].value.items : [];
  const orders = settled[5].status === "fulfilled" ? settled[5].value.items : [];
  const market = settled[6].status === "fulfilled" ? settled[6].value : null;
  const signals = settled[7].status === "fulfilled" ? settled[7].value.items : [];

  const topError =
    settled.find((x) => x.status === "rejected")?.status === "rejected"
      ? (settled.find((x) => x.status === "rejected") as PromiseRejectedResult).reason
      : null;

  const overview = computeRiskOverviewFromRuntime(runtime);
  const blockers = computeLiveBlockers({
    health: healthPack.health,
    runtime,
    liveSignal: live?.latest_signal,
    killSwitchCount: killSwitches.length,
    decisions,
  });
  const overall = computeOverallStatus(blockers);
  const assetRows = buildAssetRiskRows({
    instruments: market?.instruments ?? [],
    signals,
  });
  const portfolio = portfolioRiskSummary({ runtime, decisions, orders });

  return (
    <>
      <Header
        title={t("console.nav.risk_portfolio")}
        subtitle="Multi-Asset-Risikozentrum mit harten Live-Blockern"
        helpBriefKey="help.risk.brief"
        helpDetailKey="help.risk.detail"
      />

      {topError ? (
        <PanelDataIssue
          err={topError instanceof Error ? topError.message : String(topError)}
          diagnostic={false}
          t={t}
        />
      ) : null}

      <div className="panel">
        <h2>Risk-Uebersicht</h2>
        <div className="signal-grid">
          <div>
            <span className="label">Gesamtstatus</span>
            <strong>{overall === "ok" ? "OK" : overall === "warnung" ? "Warnung" : "Blockiert"}</strong>
          </div>
          <div>
            <span className="label">Betriebsmodus</span>
            <strong>{healthPack.health?.execution.execution_mode ?? "—"}</strong>
          </div>
          <div>
            <span className="label">Daily Loss</span>
            <strong>{overview.dailyLoss}</strong>
          </div>
          <div>
            <span className="label">Weekly Loss</span>
            <strong>{overview.weeklyLoss}</strong>
          </div>
          <div>
            <span className="label">Drawdown</span>
            <strong>{overview.drawdown}</strong>
          </div>
          <div>
            <span className="label">Margin Usage</span>
            <strong>{overview.marginUsage}</strong>
          </div>
          <div>
            <span className="label">Offene Positionen / Kandidaten</span>
            <strong>{orders.length} / {decisions.length}</strong>
          </div>
          <div>
            <span className="label">Portfolio Exposure</span>
            <strong>{overview.portfolioExposure}</strong>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          Groesste Einzelrisiken: {overview.topRisks.length ? overview.topRisks.join(" · ") : "keine Daten"}
        </p>
      </div>

      <div className="panel">
        <h2>Harte Live-Blocker</h2>
        <ul className="news-list">
          {blockers.length > 0 ? (
            blockers.map((b) => <li key={b}>{b}</li>)
          ) : (
            <li>Keine harten Live-Blocker erkannt.</li>
          )}
        </ul>
      </div>

      <div className="panel">
        <h2>Asset-Risk-Tabelle</h2>
        <div className="table-wrap">
          <table className="data-table data-table--dense">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Risk Tier</th>
                <th>Volatilitaet/ATR</th>
                <th>Spread/Liquidity</th>
                <th>Funding/OI</th>
                <th>Datenqualitaet</th>
                <th>Max Modus</th>
                <th>Blockgruende</th>
              </tr>
            </thead>
            <tbody>
              {assetRows.length > 0 ? (
                assetRows.map((row) => (
                  <tr key={row.symbol}>
                    <td>{row.symbol}</td>
                    <td>{row.riskTier}</td>
                    <td>{row.volatilityAtr}</td>
                    <td>{row.spreadLiquidity}</td>
                    <td>{row.fundingOi}</td>
                    <td>{row.dataQuality}</td>
                    <td>{row.maxMode}</td>
                    <td>{row.blockReasons.join(" · ")}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>Keine Asset-Risk-Daten verfuegbar, Live bleibt blockiert.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>Portfolio-Risk</h2>
        <div className="signal-grid">
          <div>
            <span className="label">Family Exposure</span>
            <strong>{Object.keys(portfolio.familyExposure).length}</strong>
          </div>
          <div>
            <span className="label">Direction Exposure</span>
            <strong>
              {portfolio.directionExposure == null ? "—" : `${(portfolio.directionExposure * 100).toFixed(1)}%`}
            </strong>
          </div>
          <div>
            <span className="label">Cluster/Korrelation</span>
            <strong>{portfolio.cluster == null ? "—" : `${(portfolio.cluster * 100).toFixed(1)}%`}</strong>
          </div>
          <div>
            <span className="label">Pending mirror trades</span>
            <strong>{portfolio.pendingMirrorTrades}</strong>
          </div>
          <div>
            <span className="label">Open orders notional</span>
            <strong>
              {portfolio.openOrdersNotional == null
                ? "—"
                : `${(portfolio.openOrdersNotional * 100).toFixed(1)}%`}
            </strong>
          </div>
          <div>
            <span className="label">Open orders count</span>
            <strong>{portfolio.openOrdersCount}</strong>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>
          Live block reasons: {portfolio.liveBlockReasons.join(" · ")}
        </p>
      </div>
    </>
  );
}
