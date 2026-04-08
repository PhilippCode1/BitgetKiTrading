import Link from "next/link";

import { PlatformExecutionStreamsGrid } from "@/components/console/PlatformExecutionStreamsGrid";
import {
  buildCoreSymbolRows,
  MARKET_UNIVERSE_CORE_SYMBOLS,
} from "@/lib/market-universe-lineage";
import { consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type {
  MarketUniverseInstrumentItem,
  SystemHealthResponse,
} from "@/lib/types";

type Props = Readonly<{
  health: SystemHealthResponse | null;
  instruments: readonly MarketUniverseInstrumentItem[];
}>;

/**
 * Sprint 2: LIVE/SHADOW/PAPER und technische Datenpfade sichtbar —
 * Market-Stream-Telemetrie, Broker-Reconcile, Kerzen/SIGNAL-Zeit, Kernsymbole.
 */
export async function MarketUniverseDataLineagePanel({
  health,
  instruments,
}: Props) {
  const t = await getServerTranslator();
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

      <PlatformExecutionStreamsGrid health={health} variant="bare" />

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
