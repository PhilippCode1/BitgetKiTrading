import { Header } from "@/components/layout/Header";
import { SafetyCommandActions } from "@/components/safety/SafetyCommandActions";
import { fetchLiveBrokerKillSwitchActive, fetchLiveBrokerRuntime, fetchSystemHealthBestEffort } from "@/lib/api";
import type { LiveBrokerRuntimeItem } from "@/lib/types";

function statusLabel(value: unknown, okValue: string, unknownLabel = "Unbekannt"): string {
  if (typeof value !== "string" || !value.trim()) return unknownLabel;
  return value === okValue ? "OK" : value;
}

function boolLabel(value: boolean | null | undefined): string {
  if (value === true) return "Aktiv/Ja";
  if (value === false) return "Inaktiv/Nein";
  return "Unbekannt";
}

function buildNoGoReasons(runtime: LiveBrokerRuntimeItem | null, hasKillSwitch: boolean, healthMissing: boolean): string[] {
  const reasons: string[] = [];
  const reconcileStatus = String(runtime?.status ?? "").toLowerCase();
  if (!runtime) reasons.push("Live-Broker-Runtime nicht verbunden.");
  if (hasKillSwitch) reasons.push("Kill-Switch aktiv.");
  if (runtime?.safety_latch_active === true) reasons.push("Safety-Latch aktiv.");
  if (!reconcileStatus || reconcileStatus === "unknown" || reconcileStatus === "stale" || reconcileStatus === "fail") {
    reasons.push("Reconcile ist unbekannt, stale oder fail.");
  }
  const truth = runtime?.upstream_ok;
  if (truth !== true) reasons.push("Exchange-Truth fehlt oder ist nicht geprüft.");
  if (healthMissing) reasons.push("System-Health nicht geladen.");
  return reasons;
}

export const dynamic = "force-dynamic";

export default async function SafetyCenterPage() {
  const [runtimeRes, killRes, healthRes] = await Promise.allSettled([
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchSystemHealthBestEffort(),
  ]);

  const runtime = runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const killActiveCount = killRes.status === "fulfilled" ? (killRes.value.items ?? []).length : 0;
  const health = healthRes.status === "fulfilled" ? healthRes.value.health : null;

  const mode = runtime?.execution_mode ?? "unknown";
  const liveLane = runtime?.operator_live_submission?.lane ?? "live_lane_unknown";
  const reconcileStatus = runtime?.status ?? "unknown";
  const exchangeTruth = runtime?.upstream_ok === true ? "vorhanden" : runtime?.upstream_ok === false ? "fehlt" : "nicht geprüft";
  const bitgetPrivate = runtime?.bitget_private_status;
  const readiness =
    bitgetPrivate?.public_api_ok === true && bitgetPrivate?.private_api_configured === true
      ? "public ok / private readonly ok"
      : "unknown";

  const assetCounts = runtime?.instrument_catalog?.counts ?? {};
  const chartFaehig = Number(assetCounts.catalog_total ?? 0);
  const shadowFaehig = Number(assetCounts.shadow_allowed ?? 0);
  const liveFaehig = Number(assetCounts.live_allowed ?? 0);
  const blockiert = Number(assetCounts.blocked ?? 0);

  const noGoReasons = buildNoGoReasons(runtime, killActiveCount > 0, !health);
  const liveBlocked = noGoReasons.length > 0;

  return (
    <>
      <Header
        title="Sicherheitszentrale"
        subtitle="Kill-Switch, Safety-Latch, Reconcile, Live-Pause und Emergency-Flatten in einer deutschen Kontrollansicht."
      />

      <div className="panel">
        <h2>Gesamtstatus</h2>
        <p>
          Live-Trading-Status:{" "}
          <strong>{liveBlocked ? "Blockiert" : "Vorbereitet (nächster Gate-Schritt)"}</strong>
        </p>
        <p className="muted small">
          Kritische Unknown-Zustände werden fail-closed als blockierend behandelt.
        </p>
      </div>

      <div className="panel">
        <h2>Sicherheitskarten</h2>
        <div className="table-wrap">
          <table className="data-table data-table--dense">
            <thead>
              <tr>
                <th>Karte</th>
                <th>Status</th>
                <th>Hinweis</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Systemmodus</td>
                <td>{mode}</td>
                <td>local/paper/shadow/staging/live</td>
              </tr>
              <tr>
                <td>Live-Trading-Status</td>
                <td>{liveLane}</td>
                <td>deaktiviert, vorbereitet, blockiert, freigegeben, pausiert</td>
              </tr>
              <tr>
                <td>Kill-Switch</td>
                <td>{killActiveCount > 0 ? "Aktiv" : "Inaktiv"}</td>
                <td>Aktive Events: {killActiveCount}</td>
              </tr>
              <tr>
                <td>Safety-Latch</td>
                <td>{boolLabel(runtime?.safety_latch_active)}</td>
                <td>Release erforderlich bei aktivem Latch</td>
              </tr>
              <tr>
                <td>Reconcile</td>
                <td>{statusLabel(reconcileStatus, "ok")}</td>
                <td>Stale/Fail/Unknown blockieren Live</td>
              </tr>
              <tr>
                <td>Exchange-Truth</td>
                <td>{exchangeTruth}</td>
                <td>Fehlt/nicht geprüft =&gt; blockierend</td>
              </tr>
              <tr>
                <td>Bitget-Readiness</td>
                <td>{readiness}</td>
                <td>Write bleibt verboten ohne separate sichere Freigabe</td>
              </tr>
              <tr>
                <td>Asset-Freigabe</td>
                <td>
                  chartfähig={chartFaehig}, shadowfähig={shadowFaehig}, livefähig={liveFaehig}, blockiert={blockiert}
                </td>
                <td>Werte aus Instrumentenkatalog-Snapshot</td>
              </tr>
              <tr>
                <td>Notfallaktionen</td>
                <td>Simulation/gesicherte Pfade</td>
                <td>Keine direkte Echtgeld-Order aus dieser UI</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>Aktuelle No-Go-Gründe (Deutsch)</h2>
        {noGoReasons.length ? (
          <ul className="news-list">
            {noGoReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">Keine akuten No-Go-Gründe im aktuellen Snapshot.</p>
        )}
        <p className="muted small">
          Nicht handelbar, weil kritische Sicherheitszustände fehlen oder blockieren.
        </p>
      </div>

      <SafetyCommandActions />
    </>
  );
}
