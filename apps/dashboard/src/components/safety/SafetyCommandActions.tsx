"use client";

import { useMemo, useState } from "react";

type ActionItem = Readonly<{
  id: string;
  title: string;
  description: string;
  hint: string;
  dangerous?: boolean;
}>;

const ACTIONS: readonly ActionItem[] = [
  {
    id: "pause-live",
    title: "Live pausieren",
    description: "Setzt die Plattform in einen blockierenden Sicherheitszustand.",
    hint: "Nur Simulation in der Oberfläche. Keine direkte Order-Aktion.",
    dangerous: true,
  },
  {
    id: "arm-kill-switch",
    title: "Kill-Switch armieren",
    description: "Aktiviert den globalen Not-Stopp für neue normale Orders.",
    hint: "Nur über sichere Backend-Pfade mit Audit; hier nur Simulation.",
    dangerous: true,
  },
  {
    id: "cancel-all",
    title: "Cancel-All anzeigen/simulieren",
    description: "Zeigt den sicheren Cancel-All-Pfad für offene Orders.",
    hint: "Keine direkte Ausführung in dieser UI.",
  },
  {
    id: "emergency-flatten",
    title: "Emergency-Flatten (reduce-only)",
    description:
      "Notfallpfad zum sicheren Schließen bestehender Positionen ohne neue Positionen.",
    hint: "Nur als reduce-only zulässig, keine neue Positionsöffnung.",
    dangerous: true,
  },
];

export function SafetyCommandActions() {
  const [selected, setSelected] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const selectedAction = useMemo(
    () => ACTIONS.find((item) => item.id === selected) ?? null,
    [selected],
  );

  return (
    <div className="panel">
      <h2>Sicherheitsaktionen (gesichert/simuliert)</h2>
      <p className="muted small">
        Diese Oberfläche löst keine direkten Echtgeld-Orders aus. Gefährliche
        Aktionen erfordern eine explizite Bestätigung und Audit über sichere
        Backend-Endpunkte.
      </p>
      <div className="table-wrap">
        <table className="data-table data-table--dense">
          <thead>
            <tr>
              <th>Aktion</th>
              <th>Beschreibung</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {ACTIONS.map((action) => (
              <tr key={action.id}>
                <td>{action.title}</td>
                <td>{action.description}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => {
                      setSelected(action.id);
                      setConfirmed(false);
                    }}
                  >
                    Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedAction ? (
        <div
          className="panel"
          style={{ marginTop: "1rem", border: "1px solid var(--border-muted)" }}
        >
          <h3>{selectedAction.title}</h3>
          <p>{selectedAction.description}</p>
          <p className="muted small">{selectedAction.hint}</p>
          <label className="muted small" style={{ display: "block", marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />{" "}
            Ich bestätige: Modus und Risiko wurden geprüft, Audit ist erforderlich.
          </label>
          <button
            type="button"
            disabled={!confirmed}
            aria-disabled={!confirmed}
            title={!confirmed ? "Bestätigung erforderlich" : "Simulation starten"}
          >
            {selectedAction.dangerous
              ? "Gefährliche Aktion nur mit Bestätigung (Simulation)"
              : "Simulation anzeigen"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
