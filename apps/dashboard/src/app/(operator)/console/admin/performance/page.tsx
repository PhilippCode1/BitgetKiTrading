import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { fetchAdminPerformanceOverview } from "@/lib/api";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { canAccessAdminViaServer } from "@/lib/operator-session";
import type { AdminPerformanceOverviewResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AdminPerformancePage() {
  const t = await getServerTranslator();
  const ok = await canAccessAdminViaServer();
  if (!ok) {
    return (
      <>
        <Header
          title={t("pages.adminHub.performanceTitle")}
          subtitle={t("pages.adminPage.subtitleRead")}
        />
        <div className="panel" role="alert">
          <p className="msg-err degradation-inline" style={{ margin: 0 }}>
            {t("pages.adminPage.deniedBody")}
          </p>
        </div>
      </>
    );
  }

  let err: string | null = null;
  let data: AdminPerformanceOverviewResponse | null = null;
  try {
    data = await fetchAdminPerformanceOverview();
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const paper = data?.paper;
  const live = data?.live;

  return (
    <>
      <Header
        title={t("pages.adminHub.performanceTitle")}
        subtitle={t("pages.adminHub.performanceSubtitle")}
      />
      <p className="muted small admin-hub__back">
        <Link href={`${CONSOLE_BASE}/admin`}>
          {t("pages.adminHub.backCockpit")}
        </Link>
      </p>
      <PanelDataIssue err={err} diagnostic={true} t={t} />
      {!err && data ? (
        <>
          <div className="panel">
            <h2>{t("pages.adminHub.performancePaperHeading")}</h2>
            <p className="muted small" style={{ marginTop: 0 }}>
              {t("pages.adminHub.performanceAsOf", {
                ms: String(data.as_of_ms),
              })}
            </p>
            <ul className="news-list">
              <li>
                {t("pages.adminHub.performanceOpenPaper")}:{" "}
                <strong>{paper?.open_positions ?? "—"}</strong>
              </li>
              <li>
                {t("pages.adminHub.performanceClosedTotal")}:{" "}
                <strong>{paper?.closed_trades_total ?? "—"}</strong>
              </li>
              <li>
                {t("pages.adminHub.performanceClosed30d")}:{" "}
                <strong>{paper?.closed_trades_last_30d ?? "—"}</strong>
              </li>
              <li>
                {t("pages.adminHub.performancePnl30d")}:{" "}
                <strong>
                  {paper?.sum_realized_pnl_net_usdt_30d ?? "—"} USDT
                </strong>{" "}
                <span className="muted">
                  ({t("pages.adminHub.performancePnl30dHint")})
                </span>
              </li>
            </ul>
          </div>
          <div className="panel">
            <h2>{t("pages.adminHub.performanceLiveHeading")}</h2>
            <ul className="news-list">
              <li>
                {t("pages.adminHub.performanceFills30d")}:{" "}
                <strong>{live?.fills_last_30d ?? "—"}</strong>
              </li>
              <li>
                {t("pages.adminHub.performanceOrdersOpen")}:{" "}
                <strong>{live?.orders_non_terminal_count ?? "—"}</strong>
              </li>
            </ul>
            {live?.note_de ? (
              <p className="muted small">{live.note_de}</p>
            ) : null}
          </div>
        </>
      ) : null}
    </>
  );
}
