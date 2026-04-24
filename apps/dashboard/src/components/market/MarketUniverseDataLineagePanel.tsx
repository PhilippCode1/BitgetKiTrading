import Link from "next/link";

import { PlatformExecutionStreamsGrid } from "@/components/console/PlatformExecutionStreamsGrid";
import { MarketUniverseDataLineageTableClient } from "@/components/market/MarketUniverseDataLineageTableClient";
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
  const streamSymbol = coreRows[0]?.symbol ?? "BTCUSDT";

  return (
    <section
      className="panel market-universe-lineage"
      data-testid="market-universe-lineage"
      aria-label={t("pages.marketUniverse.lineageTitle")}
    >
      <h2>{t("pages.marketUniverse.lineageTitle")}</h2>
      <p className="muted small">{t("pages.marketUniverse.lineageLead")}</p>

      <PlatformExecutionStreamsGrid health={health} variant="bare" />

      <MarketUniverseDataLineageTableClient
        coreRows={coreRows}
        streamSymbol={streamSymbol}
        i18n={{
          sub: t("pages.marketUniverse.lineageCoreSymbols"),
          thSymbol: t("pages.marketUniverse.lineageThSymbol"),
          thRegistry: t("pages.marketUniverse.lineageThRegistry"),
          thLive: t("pages.marketUniverse.lineageThLive"),
          thSubscribe: t("pages.marketUniverse.lineageThSubscribe"),
          thTrade: t("pages.marketUniverse.lineageThTrade"),
          thStatus: t("pages.marketUniverse.lineageThStatus"),
          thChart: t("pages.marketUniverse.lineageThChart"),
          thPipelineLag: t("pages.marketUniverse.lineageThPipelineLag"),
          thVpin: t("pages.marketUniverse.lineageThVpin"),
          yes: t("account.yes"),
          no: t("account.no"),
          openChart: t("pages.marketUniverse.lineageOpenChart"),
          pulseStreamLabel: t("pages.marketUniverse.pulseStreamLabel"),
          pulseLagLabel: t("pages.marketUniverse.pulseLagLabel"),
          pulseNoSse: t("pages.marketUniverse.pulseNoSse"),
          notApplicableRow: t("pages.marketUniverse.pulseNotOtherSymbol"),
        }}
      />

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
