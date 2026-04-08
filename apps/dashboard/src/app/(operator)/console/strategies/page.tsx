import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { ConsoleSurfaceNotice } from "@/components/console/ConsoleSurfaceNotice";
import { Header } from "@/components/layout/Header";
import { SignalPathPlaybooksPanel } from "@/components/panels/SignalPathPlaybooksPanel";
import { StrategiesTable } from "@/components/tables/StrategiesTable";
import { fetchStrategies } from "@/lib/api";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function StrategiesPage({
  searchParams = {},
}: {
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  let data: import("@/lib/types").StrategiesListResponse | null = null;
  let error: string | null = null;
  try {
    data = await fetchStrategies();
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const items = data?.items ?? [];
  const playbooks = data?.signal_path_playbooks ?? [];

  return (
    <>
      <Header
        title={t("console.nav.strategies")}
        subtitle={t("pages.strategiesList.subtitle")}
      />
      <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
      {data?.message && String(data.message).trim() !== "" ? (
        <ConsoleSurfaceNotice
          t={t}
          variant="soft"
          titleKey="ui.surfaceState.degraded.title"
          body={data.message}
          refreshKey="ui.surfaceState.degraded.refreshHint"
          showStateActions
          style={{ marginBottom: 12 }}
        />
      ) : null}
      <StrategiesTable
        items={items}
        emptyMessage={t("pages.strategiesList.tableEmpty")}
        detailLinkLabel={t("pages.strategiesList.detailLink")}
        signalPathHeader={t("pages.strategiesList.signalPathCol")}
        statusLabelNotSet={t("pages.strategiesList.statusNotSet")}
        thName={t("pages.strategiesList.thName")}
        thStatus={t("pages.strategiesList.thStatus")}
        thInstrument={t("pages.strategiesList.thInstrument")}
        thVersion={t("pages.strategiesList.thVersion")}
        thPfRoll={t("pages.strategiesList.thPfRoll")}
        thWinRoll={t("pages.strategiesList.thWinRoll")}
        mobileListAria={t("pages.strategiesList.mobileListAria")}
        mobileInstrumentLabel={t("pages.strategiesList.thInstrument")}
        mobilePfLabel={t("pages.strategiesList.mobilePfLabel")}
        mobileWinLabel={t("pages.strategiesList.mobileWinLabel")}
        rollingMetricsThTitle={t("pages.strategiesList.rollingMetricsThTitle")}
        rollingNoSnapshotNote={t("pages.strategiesList.rollingNoSnapshotNote")}
      />
      <SignalPathPlaybooksPanel items={playbooks} t={t} />
    </>
  );
}
