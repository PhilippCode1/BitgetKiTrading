import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { consolePath } from "@/lib/console-paths";
import {
  buildEvidenceCards,
  readOwnerPrivateLiveReleaseGate,
  resolveDashboardRepoRoot,
} from "@/lib/evidence-console";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const t = await getServerTranslator();
  const repoRoot = resolveDashboardRepoRoot();
  const cards = buildEvidenceCards({ rootDir: repoRoot });
  const ownerGate = readOwnerPrivateLiveReleaseGate(repoRoot);
  const liveBlockers = cards.filter((c) => c.blocksLive);

  return (
    <>
      <Header
        title={t("console.reportsPage.title")}
        subtitle={t("console.reportsPage.subtitle")}
      />
      <div className="panel">
        <h2>{t("console.reportsPage.goNoGoTitle")}</h2>
        <p>
          {t("console.reportsPage.cardsTotal")}: <strong>{cards.length}</strong>
        </p>
        <p>
          {t("console.reportsPage.liveBlockers")}:{" "}
          <strong>{liveBlockers.length}</strong>
        </p>
        <p className="muted small">{t("console.reportsPage.failClosedNote")}</p>
      </div>

      <div className="panel">
        <h2>{t("console.reportsPage.ownerTitle")}</h2>
        <p>
          {t("console.reportsPage.ownerFile")}:{" "}
          <span className="mono-small">{ownerGate.fileRelative}</span> (
          {t("console.reportsPage.ownerNotCommitted")})
        </p>
        <p>
          {t("console.reportsPage.ownerStatus")}:{" "}
          <strong>
            {ownerGate.payloadValid
              ? t("console.reportsPage.ownerValid")
              : ownerGate.filePresent
                ? t("console.reportsPage.ownerInvalid")
                : t("console.reportsPage.ownerMissing")}
          </strong>
          {ownerGate.scorecardBlocksPrivateLive
            ? t("console.reportsPage.ownerBlocksPrivate")
            : ""}
        </p>
        <p className="muted small">
          {ownerGate.payloadValid
            ? t("console.reportsPage.ownerSummaryValid")
            : ownerGate.filePresent
              ? t("console.reportsPage.ownerSummaryInvalid")
              : t("console.reportsPage.ownerSummaryMissing")}
        </p>
        <p className="muted small">
          {t("console.reportsPage.template")}:{" "}
          <span className="mono-small">{ownerGate.templateRelative}</span> —{" "}
          {t("console.reportsPage.execution")}:{" "}
          <span className="mono-small">
            scripts/production_readiness_scorecard.py
          </span>
        </p>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("console.reportsPage.colEvidence")}</th>
              <th>{t("console.reportsPage.colStatus")}</th>
              <th>{t("console.reportsPage.colLastReport")}</th>
              <th>{t("console.reportsPage.colDate")}</th>
              <th>{t("console.reportsPage.colGitSha")}</th>
              <th>{t("console.reportsPage.colLiveImpact")}</th>
              <th>{t("console.reportsPage.colNextStep")}</th>
            </tr>
          </thead>
          <tbody>
            {cards.map((card) => (
              <tr key={card.id}>
                <td>{card.title}</td>
                <td>
                  <span
                    className={
                      card.status === "verified"
                        ? "status-pill status-pill--ok"
                        : "status-pill status-pill--warn"
                    }
                  >
                    {card.statusLabelDe}
                  </span>
                </td>
                <td>
                  {card.lastReportPath ? (
                    <span className="mono-small">{card.lastReportPath}</span>
                  ) : (
                    <span className="muted">
                      {t("console.reportsPage.evidenceMissing")}
                    </span>
                  )}
                </td>
                <td>{card.lastReportDate ?? "—"}</td>
                <td className="mono-small">{card.gitSha ?? "—"}</td>
                <td>{card.liveImpactDe}</td>
                <td>{card.nextStepDe}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>{t("console.reportsPage.docsTitle")}</h2>
        <ul className="news-list">
          <li>
            <Link href={consolePath("system-health-map")}>
              {t("console.reportsPage.linkHealth")}
            </Link>
          </li>
          <li>
            <span className="mono-small">tools/check_10_10_evidence.py</span>
          </li>
          <li>
            <span className="mono-small">
              scripts/production_readiness_scorecard.py
            </span>
          </li>
        </ul>
        <p className="muted small">{t("console.reportsPage.noUiScripts")}</p>
      </div>
    </>
  );
}
