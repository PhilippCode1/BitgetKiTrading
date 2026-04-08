import Link from "next/link";

import { IntegrationServiceProbeTable } from "@/components/panels/IntegrationServiceProbeTable";
import { IntegrationSummaryBanner } from "@/components/panels/IntegrationSummaryBanner";
import { IntegrationsMatrixPanel } from "@/components/panels/IntegrationsMatrixPanel";
import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchSystemHealthCached } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function IntegrationsCheckPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let health = null as Awaited<
    ReturnType<typeof fetchSystemHealthCached>
  > | null;
  let err: string | null = null;
  try {
    health = await fetchSystemHealthCached();
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  return (
    <>
      <Header
        title={t("pages.integrations.title")}
        subtitle={t("pages.integrations.subtitle")}
        helpBriefKey="help.monitor.brief"
        helpDetailKey="help.monitor.detail"
      />
      <p className="muted small">
        <Link href={consolePath("health")}>
          {t("pages.integrations.linkHealth")}
        </Link>
        {" · "}
        <a href="/api/dashboard/edge-status" target="_blank" rel="noreferrer">
          {t("live.terminal.edgeStatusLink")}
        </a>
      </p>
      {err ? (
        <div className="panel" role="status">
          <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
        </div>
      ) : null}
      {health ? (
        <IntegrationSummaryBanner matrix={health.integrations_matrix} />
      ) : null}
      {health ? (
        <IntegrationsMatrixPanel matrix={health.integrations_matrix} />
      ) : null}
      {health ? (
        <IntegrationServiceProbeTable services={health.services} />
      ) : null}
    </>
  );
}
