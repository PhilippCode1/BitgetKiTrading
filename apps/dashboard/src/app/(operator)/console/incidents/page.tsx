import type { CSSProperties } from "react";

import { Header } from "@/components/layout/Header";
import {
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerRuntime,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { buildOperatorAlertsFromConsoleSnapshot } from "@/lib/operator-alerts-view-model";
import type { OperatorAlertView, OperatorSeverity } from "@/lib/operator-alerts-view-model";

export const dynamic = "force-dynamic";

function severityFrame(sev: OperatorSeverity): CSSProperties {
  if (sev === "P0") {
    return {
      borderLeft: "4px solid var(--danger, #e07070)",
      background: "var(--danger-muted, rgba(224, 112, 112, 0.12))",
    };
  }
  if (sev === "P1") {
    return {
      borderLeft: "4px solid var(--warning, #d4a017)",
      background: "rgba(212, 160, 23, 0.08)",
    };
  }
  if (sev === "P2") {
    return { borderLeft: "4px solid var(--fg-muted, #888)" };
  }
  return { borderLeft: "4px solid var(--border, #444)" };
}

function AlertCard({ alert }: { alert: OperatorAlertView }) {
  return (
    <article className="panel operator-alert-card" style={severityFrame(alert.severity)}>
      <header className="operator-alert-card__head">
        <span className="operator-alert-card__sev" data-severity={alert.severity}>
          {alert.severity}
        </span>
        <h3 className="operator-alert-card__title">{alert.titel_de}</h3>
      </header>
      <p>{alert.beschreibung_de}</p>
      <dl className="operator-alert-card__dl">
        <div>
          <dt>Live blockiert</dt>
          <dd>{alert.live_blockiert ? "Ja" : "Nein"}</dd>
        </div>
        <div>
          <dt>Betroffene Komponente</dt>
          <dd>{alert.betroffene_komponente}</dd>
        </div>
        <div>
          <dt>Betroffene Assets</dt>
          <dd>{alert.betroffene_assets.length ? alert.betroffene_assets.join(", ") : "—"}</dd>
        </div>
        <div>
          <dt>Empfohlene Aktion</dt>
          <dd>{alert.empfohlene_aktion_de}</dd>
        </div>
        <div>
          <dt>Nächster sicherer Schritt</dt>
          <dd>{alert.nächster_sicherer_schritt_de}</dd>
        </div>
        <div>
          <dt>Zeitpunkt</dt>
          <dd>{alert.zeitpunkt}</dd>
        </div>
        <div>
          <dt>Korrelation</dt>
          <dd className="muted small">{alert.korrelation_id}</dd>
        </div>
      </dl>
      {alert.technische_details_redacted ? (
        <p className="muted small">
          <strong>Technische Details (redacted):</strong> {alert.technische_details_redacted}
        </p>
      ) : null}
    </article>
  );
}

export default async function IncidentsPage() {
  const [runtimeRes, killRes, healthRes] = await Promise.allSettled([
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchSystemHealthBestEffort(),
  ]);

  const runtime = runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const killCount = killRes.status === "fulfilled" ? (killRes.value.items ?? []).length : 0;
  const health = healthRes.status === "fulfilled" ? healthRes.value.health : null;

  const activeAlerts = buildOperatorAlertsFromConsoleSnapshot({
    health,
    runtime,
    killSwitchActiveCount: killCount,
  });

  const aktivListe = activeAlerts.filter((a) => a.aktiv);
  const historischListe = activeAlerts.filter((a) => !a.aktiv);

  return (
    <>
      <Header
        title="Vorfälle & Warnungen"
        subtitle="Priorisierte Operator-Meldungen (P0–P3) aus Health und Live-Broker — deutsch, ohne Secrets, sortiert nach Kritikalität."
      />

      <div className="panel">
        <h2>Eskalationslogik</h2>
        <ul className="muted small">
          <li>
            <strong>P0</strong>: sofortiger Live-Blocker — immer mit klarem Hinweis, ob Live blockiert ist.
          </li>
          <li>
            <strong>P1</strong>: kritische Störung, Live blockiert oder stark eingeschränkt.
          </li>
          <li>
            <strong>P2</strong>: Warnung, Beobachtung und geplante Maßnahme.
          </li>
          <li>
            <strong>P3</strong>: Hinweis, kein akuter Eingriff.
          </li>
        </ul>
        <p className="muted small">
          Fehlende Daten werden nicht als „OK“ gewertet. Historische Einträge erscheinen unten, sobald eine
          Archiv-Anbindung existiert (derzeit meist leer).
        </p>
      </div>

      <div className="panel">
        <h2>Aktive Meldungen</h2>
        {aktivListe.length === 0 ? (
          <p className="muted">Keine aktiven Einträge aus den angebundenen Quellen.</p>
        ) : (
          <div className="stack" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {aktivListe.map((a) => (
              <AlertCard key={a.korrelation_id} alert={a} />
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Historische Meldungen</h2>
        {historischListe.length === 0 ? (
          <p className="muted">
            Noch keine Archiv-Anbindung — nur aktuelle Snapshots werden angezeigt.
          </p>
        ) : (
          <div className="stack" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {historischListe.map((a) => (
              <AlertCard key={a.korrelation_id} alert={a} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
