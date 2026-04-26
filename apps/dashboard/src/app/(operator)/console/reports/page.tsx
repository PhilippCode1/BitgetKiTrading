import Link from "next/link";

import { Header } from "@/components/layout/Header";
import { consolePath } from "@/lib/console-paths";
import {
  buildEvidenceCards,
  readOwnerPrivateLiveReleaseGate,
  resolveDashboardRepoRoot,
} from "@/lib/evidence-console";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
  const repoRoot = resolveDashboardRepoRoot();
  const cards = buildEvidenceCards({ rootDir: repoRoot });
  const ownerGate = readOwnerPrivateLiveReleaseGate(repoRoot);
  const liveBlockers = cards.filter((c) => c.blocksLive);

  return (
    <>
      <Header
        title="Reports, Evidence & Go/No-Go"
        subtitle="Shadow-Burn-in, Backtest, Restore und Readiness mit ehrlichem Status statt Behauptungen."
      />
      <div className="panel">
        <h2>Go/No-Go Gesamtbild</h2>
        <p>
          Karten gesamt: <strong>{cards.length}</strong>
        </p>
        <p>
          Live-blockierende Nachweise: <strong>{liveBlockers.length}</strong>
        </p>
        <p className="muted small">
          Kein 10/10 ohne verifizierten Nachweis. Fehlende Reports bleiben fail-closed.
        </p>
      </div>

      <div className="panel">
        <h2>Maschinelle Owner-Freigabe (Private Live)</h2>
        <p>
          Datei: <span className="mono-small">{ownerGate.fileRelative}</span> (gitignored,
          nicht committen)
        </p>
        <p>
          Status:{" "}
          <strong>
            {ownerGate.payloadValid
              ? "Gültige lokale Freigabe"
              : ownerGate.filePresent
                ? "Datei ungültig"
                : "Datei fehlt"}
          </strong>
          {ownerGate.scorecardBlocksPrivateLive ? " — blockiert private_live_allowed" : ""}
        </p>
        <p className="muted small">{ownerGate.summaryDe}</p>
        <p className="muted small">
          Template: <span className="mono-small">{ownerGate.templateRelative}</span> — Ausführung:{" "}
          <span className="mono-small">scripts/production_readiness_scorecard.py</span>
        </p>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Evidence-Karte</th>
              <th>Status</th>
              <th>Letzter Report</th>
              <th>Datum</th>
              <th>Git SHA</th>
              <th>Live-Auswirkung</th>
              <th>Nächster Schritt</th>
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
                    <span className="muted">Nachweis fehlt</span>
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
        <h2>Evidence-Dokumentation und Skripte</h2>
        <ul className="news-list">
          <li>
            <Link href={consolePath("system-health-map")}>Systemstatus prüfen</Link>
          </li>
          <li>
            <span className="mono-small">tools/check_10_10_evidence.py</span>
          </li>
          <li>
            <span className="mono-small">scripts/production_readiness_scorecard.py</span>
          </li>
        </ul>
        <p className="muted small">
          Diese Seite startet keine Scripts aus der UI. Ausführung erfolgt nur explizit im
          kontrollierten Operator-Workflow.
        </p>
      </div>
    </>
  );
}
