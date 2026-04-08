import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { MarketCapabilityMatrixTable } from "@/components/market/MarketCapabilityMatrixTable";
import { fetchMarketUniverseStatus } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function CapabilitiesPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let data: import("@/lib/types").MarketUniverseStatusResponse | null = null;
  let error: string | null = null;
  try {
    data = await fetchMarketUniverseStatus();
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.capabilities.title")}
        subtitle={t("pages.capabilities.subtitle")}
      />
      <p className="muted small">
        {t("pages.capabilities.fullDataLead")}{" "}
        <Link href={consolePath("market-universe")}>
          {t("console.nav.market_universe")}
        </Link>
        .
      </p>
      <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
      {!error && !data ? (
        <div className="panel" role="status">
          <h2>{t("pages.capabilities.unavailableTitle")}</h2>
          <p className="muted">{t("pages.capabilities.unavailableBody")}</p>
          <p className="muted small">
            <Link href={consolePath("health")}>{t("console.nav.health")}</Link>
            {" · "}
            <a
              href="/api/dashboard/edge-status"
              target="_blank"
              rel="noreferrer"
            >
              {t("live.terminal.edgeStatusLink")}
            </a>
          </p>
        </div>
      ) : null}
      {!data ? null : (
        <div className="panel">
          <h2>{t("pages.capabilities.matrixTitle")}</h2>
          <p className="muted small">{t("pages.capabilities.matrixLead")}</p>
          <MarketCapabilityMatrixTable categories={data.categories} />
        </div>
      )}
    </>
  );
}
