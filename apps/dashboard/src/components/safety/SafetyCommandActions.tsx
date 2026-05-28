"use client";

import { useMemo, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

type ActionId =
  | "pause-live"
  | "arm-kill-switch"
  | "cancel-all"
  | "emergency-flatten";

const ACTION_IDS: readonly ActionId[] = [
  "pause-live",
  "arm-kill-switch",
  "cancel-all",
  "emergency-flatten",
];

function actionKey(id: ActionId, field: "Title" | "Desc" | "Hint"): string {
  const base =
    id === "pause-live"
      ? "pauseLive"
      : id === "arm-kill-switch"
        ? "armKill"
        : id === "cancel-all"
          ? "cancelAll"
          : "flatten";
  return `console.safetyCommandActions.${base}${field}`;
}

export function SafetyCommandActions() {
  const { t } = useI18n();
  const [selected, setSelected] = useState<ActionId | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const actions = useMemo(
    () =>
      ACTION_IDS.map((id) => ({
        id,
        title: t(actionKey(id, "Title")),
        description: t(actionKey(id, "Desc")),
        hint: t(actionKey(id, "Hint")),
        dangerous: id !== "cancel-all",
      })),
    [t],
  );

  const selectedAction = useMemo(
    () => actions.find((item) => item.id === selected) ?? null,
    [actions, selected],
  );

  return (
    <div className="panel">
      <h2>{t("console.safetyCommandActions.title")}</h2>
      <p className="muted small">{t("console.safetyCommandActions.lead")}</p>
      <div className="table-wrap">
        <table className="data-table data-table--dense">
          <thead>
            <tr>
              <th>{t("console.safetyCommandActions.colAction")}</th>
              <th>{t("console.safetyCommandActions.colDescription")}</th>
              <th>{t("console.safetyCommandActions.colStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
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
                    {selected === action.id
                      ? t("console.safetyCommandActions.selected")
                      : t("console.safetyCommandActions.select")}
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
          <label
            className="muted small"
            style={{ display: "block", marginBottom: 8 }}
          >
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />{" "}
            {t("console.safetyCommandActions.confirmLabel")}
          </label>
          <button type="button" disabled={!confirmed} aria-disabled={!confirmed}>
            {t("console.safetyCommandActions.runSimulated")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
