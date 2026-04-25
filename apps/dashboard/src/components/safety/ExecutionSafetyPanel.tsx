"use client";

import { useMemo, useState } from "react";

type ActionId =
  | "kill_switch_arm"
  | "kill_switch_release"
  | "safety_latch_release"
  | "cancel_all"
  | "emergency_flatten";

type ActionSpec = {
  id: ActionId;
  title: string;
  dangerous: boolean;
  endpoint: string | null;
  endpointAvailable: boolean;
};

const ACTIONS: readonly ActionSpec[] = [
  {
    id: "kill_switch_arm",
    title: "Kill-Switch armieren",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/kill-switch/arm",
    endpointAvailable: false,
  },
  {
    id: "kill_switch_release",
    title: "Kill-Switch freigeben",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/kill-switch/release",
    endpointAvailable: false,
  },
  {
    id: "safety_latch_release",
    title: "Safety-Latch freigeben",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/safety-latch/release",
    endpointAvailable: false,
  },
  {
    id: "cancel_all",
    title: "Cancel-All (kontrolliert)",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/orders/cancel-all",
    endpointAvailable: false,
  },
  {
    id: "emergency_flatten",
    title: "Emergency-Flatten (reduce-only)",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/emergency-flatten",
    endpointAvailable: false,
  },
];

export function actionDisabledReason(params: {
  action: ActionSpec;
  killSwitchActive: boolean;
  safetyLatchActive: boolean;
  reconcileOk: boolean;
}): string | null {
  const { action, killSwitchActive, safetyLatchActive, reconcileOk } = params;
  if (!action.endpointAvailable) return "Endpoint fehlt, Aktion ist sicher deaktiviert.";
  if (!reconcileOk) return "Reconcile nicht ok, Aktion blockiert.";
  if (killSwitchActive && action.id !== "kill_switch_release") {
    return "Kill-Switch aktiv, normale Aktionen sind blockiert.";
  }
  if (safetyLatchActive && action.id !== "safety_latch_release") {
    return "Safety-Latch aktiv, normale Aktionen sind blockiert.";
  }
  return null;
}

export function ExecutionSafetyPanel({
  killSwitchActive,
  safetyLatchActive,
  reconcileOk,
}: {
  killSwitchActive: boolean;
  safetyLatchActive: boolean;
  reconcileOk: boolean;
}) {
  const [selected, setSelected] = useState<ActionId | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const selectedAction = useMemo(
    () => ACTIONS.find((a) => a.id === selected) ?? null,
    [selected],
  );
  const disabledReason = selectedAction
    ? actionDisabledReason({
        action: selectedAction,
        killSwitchActive,
        safetyLatchActive,
        reconcileOk,
      })
    : null;

  return (
    <div className="panel">
      <h2>Safety Panel</h2>
      <p className="muted small">
        Gefaehrliche Aktionen brauchen immer Kontext, Bestaetigung und sicheren Endpoint.
      </p>
      <ul className="news-list">
        {ACTIONS.map((action) => {
          const reason = actionDisabledReason({
            action,
            killSwitchActive,
            safetyLatchActive,
            reconcileOk,
          });
          const disabled = Boolean(reason);
          return (
            <li key={action.id}>
              <button
                type="button"
                className={action.dangerous ? "public-btn danger" : "public-btn ghost"}
                title="Bestaetigungsdialog oeffnen"
                onClick={() => {
                  setSelected(action.id);
                  setConfirmed(false);
                }}
              >
                {action.title} pruefen
              </button>
              <span className="muted small">
                {" "}
                — {disabled ? reason : "Endpoint vorhanden, weiterhin nur mit Bestaetigung."}
              </span>
            </li>
          );
        })}
      </ul>
      {selectedAction ? (
        <div className="panel" role="dialog" aria-label="Bestaetigung fuer Sicherheitsaktion">
          <h3>Bestaetigung erforderlich</h3>
          <p>
            Du willst <strong>{selectedAction.title}</strong> ausfuehren. Diese Aktion ist
            potenziell gefaehrlich und darf niemals ohne klaren Sicherheitskontext laufen.
          </p>
          <label className="muted small">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />{" "}
            Ich bestaetige den Modus, die Blocker und den Notfallkontext.
          </label>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="public-btn danger"
              disabled={!confirmed || Boolean(disabledReason)}
              aria-disabled={!confirmed || Boolean(disabledReason)}
              title={disabledReason ?? "Nur freigeben, wenn Backend sicher verdrahtet ist"}
            >
              Aktion ausfuehren (derzeit deaktiviert)
            </button>
          </div>
          {disabledReason ? <p className="muted small">{disabledReason}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
