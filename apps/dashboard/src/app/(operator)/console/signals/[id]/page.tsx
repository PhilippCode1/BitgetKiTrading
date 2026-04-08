import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { ConsoleSurfaceNotice } from "@/components/console/ConsoleSurfaceNotice";
import { Header } from "@/components/layout/Header";
import { StrategyProposalDraftPanel } from "@/components/panels/StrategyProposalDraftPanel";
import { StrategySignalExplainPanel } from "@/components/panels/StrategySignalExplainPanel";
import { SignalDetailHumanSummary } from "@/components/signals/SignalDetailHumanSummary";
import { SignalDetailLiveAiSection } from "@/components/signals/SignalDetailLiveAiSection";
import { SignalDetailMarketChartBlock } from "@/components/signals/SignalDetailMarketChartBlock";
import { SignalDetailRiskStrategySection } from "@/components/signals/SignalDetailRiskStrategySection";
import { SignalDetailStoredExplainSection } from "@/components/signals/SignalDetailStoredExplainSection";
import { SignalDetailTechnicalCollapsible } from "@/components/signals/SignalDetailTechnicalCollapsible";
import { SignalDetailLlmChartProvider } from "@/components/signals/signal-detail-llm-chart-context";
import {
  fetchSignalDetail,
  fetchSignalExplain,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { executionPathFromSystemHealth } from "@/lib/execution-path-view-model";
import { normalizeChartTimeframe } from "@/lib/chart-prefs";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type P = { id: string };

function first(sp: ConsoleSearchParams, key: string): string | undefined {
  const v = sp[key];
  return Array.isArray(v) ? v[0] : v;
}

export default async function SignalDetailPage(props: {
  params: P | Promise<P>;
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(props.searchParams ?? {});
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const { id } = await Promise.resolve(props.params);
  let detail = null as Awaited<ReturnType<typeof fetchSignalDetail>> | null;
  let explain = null as Awaited<ReturnType<typeof fetchSignalExplain>> | null;
  let healthPack: Awaited<
    ReturnType<typeof fetchSystemHealthBestEffort>
  > | null = null;
  let err: string | null = null;
  try {
    const triple = await Promise.all([
      fetchSignalDetail(id),
      fetchSignalExplain(id),
      fetchSystemHealthBestEffort(),
    ]);
    detail = triple[0];
    explain = triple[1];
    healthPack = triple[2];
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  if (err || !detail) {
    return (
      <>
        <Header title={t("pages.signals.title")} />
        <div className="panel" role="status">
          {err ? (
            <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
          ) : (
            <ConsoleSurfaceNotice
              t={t}
              titleKey="pages.signalsDetail.notFoundTitle"
              bodyKey="pages.signalsDetail.notFound"
              refreshKey="ui.surfaceState.notFound.refreshHint"
              showStateActions
              wrapActions
            />
          )}
          <Link
            href={consolePath("signals")}
            className="public-btn ghost"
            style={{ marginTop: 12, display: "inline-block" }}
          >
            ← {t("pages.signalsDetail.backToList")}
          </Link>
        </div>
      </>
    );
  }

  const chartTf =
    normalizeChartTimeframe(first(sp, "timeframe")) ??
    normalizeChartTimeframe(detail.timeframe) ??
    "5m";

  const detailForLlm = { ...detail };
  delete (detailForLlm as { signal_view?: unknown }).signal_view;
  delete (detailForLlm as { signal_contract_version?: unknown })
    .signal_contract_version;
  const signalSnapshotForLlm = JSON.parse(
    JSON.stringify(detailForLlm),
  ) as Record<string, unknown>;

  const shortId = detail.signal_id.slice(0, 8);
  const reasonsJsonForAudit = explain?.reasons_json ?? detail.reasons_json;
  const executionVm = executionPathFromSystemHealth(healthPack?.health ?? null);
  const executionModeLabel =
    healthPack?.health?.execution?.execution_mode ?? null;
  const healthLoadError = healthPack?.error ?? null;

  return (
    <>
      <Header
        title={t("pages.signalsDetail.heroTitle", { symbol: detail.symbol })}
        subtitle={t("pages.signalsDetail.heroSubtitle", {
          timeframe: detail.timeframe,
          shortId,
        })}
      />
      <p>
        <Link href={consolePath("signals")}>
          ← {t("pages.signalsDetail.backToList")}
        </Link>
      </p>

      <HealthSnapshotLoadNotice
        error={healthLoadError}
        diagnostic={diagnostic}
        t={t}
      />

      <SignalDetailLlmChartProvider>
        <SignalDetailHumanSummary detail={detail} explain={explain} t={t} />

        <SignalDetailMarketChartBlock
          signalId={detail.signal_id}
          symbol={detail.symbol}
          timeframe={chartTf}
          executionVm={executionVm}
          executionModeLabel={executionModeLabel}
        />

        <SignalDetailRiskStrategySection
          detail={detail}
          explain={explain}
          t={t}
        />

        <SignalDetailStoredExplainSection
          explain={explain}
          contractVersion={detail.signal_contract_version}
          t={t}
        />

        <p className="muted small signal-detail-layer4-aside">
          {t("pages.signalsDetail.explainLayer4Aside")}
        </p>

        <SignalDetailLiveAiSection t={t}>
          <StrategySignalExplainPanel
            signalContextJson={signalSnapshotForLlm}
          />
          <StrategyProposalDraftPanel
            signalId={detail.signal_id}
            symbol={detail.symbol}
            timeframe={chartTf}
            chartContextJson={signalSnapshotForLlm}
          />
        </SignalDetailLiveAiSection>
      </SignalDetailLlmChartProvider>

      <SignalDetailTechnicalCollapsible
        detail={detail}
        reasonsJsonForAudit={reasonsJsonForAudit}
        t={t}
      />
    </>
  );
}
