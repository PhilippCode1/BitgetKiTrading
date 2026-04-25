import { Header } from "@/components/layout/Header";
import {
  fetchLiveBrokerRuntime,
  fetchLiveState,
  fetchMonitorAlertsOpen,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { buildHealthMapViewModel } from "@/lib/health-map-view-model";
import { buildSystemDiagnosticsViewModel } from "@/lib/system-diagnostics-view-model";
import { publicEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

function badgeClass(status: "ok" | "warn" | "fail" | "unknown"): string {
  if (status === "ok") return "status-pill status-pill--ok";
  if (status === "warn") return "status-pill status-pill--warn";
  if (status === "fail") return "status-pill status-pill--danger";
  return "status-pill";
}

export default async function SystemHealthMapPage() {
  const [healthRes, runtimeRes, liveRes, alertsRes] = await Promise.allSettled([
    fetchSystemHealthBestEffort(),
    fetchLiveBrokerRuntime(),
    fetchLiveState({
      symbol: publicEnv.defaultSymbol,
      timeframe: publicEnv.defaultTimeframe,
      limit: 200,
    }),
    fetchMonitorAlertsOpen(),
  ]);

  const health = healthRes.status === "fulfilled" ? healthRes.value.health : null;
  const runtime = runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const liveState = liveRes.status === "fulfilled" ? liveRes.value : null;
  const openAlerts = alertsRes.status === "fulfilled" ? alertsRes.value.items : [];
  const model = buildHealthMapViewModel({ health, runtime });
  const diagnostics = buildSystemDiagnosticsViewModel({
    health,
    runtime,
    liveState,
    openAlerts,
    healthEndpointWired: healthRes.status === "fulfilled",
  });
  const healthEndpointMissing = healthRes.status !== "fulfilled";

  return (
    <>
      <Header
        title="Systemstatus, Diagnostik & Alerts"
        subtitle="Systemzustand & Datenflüsse: Alle Services, Provider, Datenfrische und Fehler an einem Ort (fail-closed)."
      />

      <div className="panel">
        <h2>Gesamtbewertung</h2>
        <p>
          Gesamtstatus:{" "}
          <strong>{diagnostics.overallStatus}</strong>
        </p>
        <p className="muted small">
          {diagnostics.summaryReasons.join(" · ")}
        </p>
        <p>
          Live-Trading:{" "}
          <strong>{model.live_blockiert ? "Blockiert (fail-closed)" : "Nicht blockiert durch Health-Landkarte"}</strong>
        </p>
        {model.blocker_gründe_de.length > 0 ? (
          <>
            <p className="muted small">Blocker-Gründe:</p>
            <ul className="muted small">
              {model.blocker_gründe_de.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </>
        ) : null}
      </div>

      <div className="panel">
        <h2>Systemstatus-Seite</h2>
        <ul className="news-list">
          <li>DB/Redis: <strong>{diagnostics.dbStatus}</strong> / <strong>{diagnostics.redisStatus}</strong></li>
          <li>Bitget Public/Private: <strong>{diagnostics.bitgetPublicStatus}</strong> / <strong>{diagnostics.bitgetPrivateStatus}</strong></li>
          <li>LLM/News: <strong>{diagnostics.llmStatus}</strong> / <strong>{diagnostics.newsStatus}</strong></li>
          <li>Alert-/Monitor-Status: <strong>{diagnostics.alertStatus}</strong></li>
        </ul>
      </div>

      <div className="panel">
        <h2>Stale Data Diagnose</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Check</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.staleChecks.map((s) => (
                <tr key={s.key}>
                  <td>{s.label}</td>
                  <td>
                    <span className={s.stale ? "status-pill status-pill--danger" : "status-pill status-pill--ok"}>
                      {s.stale ? "stale" : "ok"}
                    </span>
                  </td>
                  <td>{s.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>Services und Datenquellen</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.serviceStatus.length === 0 ? (
                <tr>
                  <td colSpan={3} className="muted">Keine Service-Daten vorhanden.</td>
                </tr>
              ) : (
                diagnostics.serviceStatus.map((s) => (
                  <tr key={s.name}>
                    <td>{s.name}</td>
                    <td>{s.status}</td>
                    <td>{s.detail}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>Letzte kritische Fehler</h2>
        <ul className="news-list">
          {diagnostics.latestCriticalErrors.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <h3>Letzte erfolgreiche Checks</h3>
        <ul className="news-list">
          {diagnostics.latestSuccessfulChecks.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>Diagnose-Aktionen (Read-only)</h2>
        <p className="muted small">
          Keine ungefragten Produktionsnetze. Aktionen sind reine Read-only-Checks.
        </p>
        <button type="button" className="public-btn ghost" disabled title="Nur manuelle Seitenaktualisierung">
          Safe Refresh (Read-only)
        </button>
        <button
          type="button"
          className="public-btn ghost"
          disabled={healthEndpointMissing}
          title={healthEndpointMissing ? "Nicht verdrahtet: Health-Endpunkt fehlt." : "Read-only Diagnosecheck"}
          style={{ marginLeft: 8 }}
        >
          Safe Check ausführen
        </button>
        {healthEndpointMissing ? (
          <p className="muted small">Nicht verdrahtet: Health-Endpunkt aktuell nicht lesbar.</p>
        ) : null}
      </div>
    </>
  );
}
