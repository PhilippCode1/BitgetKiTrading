"use client";

import { useMemo, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

type ActionId =
  | "kill_switch_arm"
  | "kill_switch_release"
  | "safety_latch_release"
  | "cancel_all"
  | "emergency_flatten";

type ActionSpec = {
  id: ActionId;
  titleKey: string;
  dangerous: boolean;
  endpoint: string | null;
  endpointAvailable: boolean;
};

const ACTION_SPECS: readonly ActionSpec[] = [
  {
    id: "kill_switch_arm",
    titleKey: "console.executionSafetyPanel.killArm",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/kill-switch/arm",
    endpointAvailable: false,
  },
  {
    id: "kill_switch_release",
    titleKey: "console.executionSafetyPanel.killRelease",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/kill-switch/release",
    endpointAvailable: false,
  },
  {
    id: "safety_latch_release",
    titleKey: "console.executionSafetyPanel.latchRelease",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/safety-latch/release",
    endpointAvailable: false,
  },
  {
    id: "cancel_all",
    titleKey: "console.executionSafetyPanel.cancelAll",
    dangerous: true,
    endpoint: "/api/dashboard/live-broker/orders/cancel-all",
    endpointAvailable: false,
  },
  {
    id: "emergency_flatten",
    titleKey: "console.executionSafetyPanel.emergencyFlatten",
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
  t: (key: string) => string;
}): string | null {
  const { action, killSwitchActive, safetyLatchActive, reconcileOk, t } =
    params;
  if (!action.endpointAvailable)
    return t("console.executionSafetyPanel.reasonEndpointMissing");
  if (!reconcileOk) return t("console.executionSafetyPanel.reasonReconcile");
  if (killSwitchActive && action.id !== "kill_switch_release") {
    return t("console.executionSafetyPanel.reasonKillSwitch");
  }
  if (safetyLatchActive && action.id !== "safety_latch_release") {
    return t("console.executionSafetyPanel.reasonSafetyLatch");
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
  const { t } = useI18n();
  const [selected, setSelected] = useState<ActionId | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const selectedAction = useMemo(
    () => ACTION_SPECS.find((a) => a.id === selected) ?? null,
    [selected],
  );
  const disabledReason = selectedAction
    ? actionDisabledReason({
        action: selectedAction,
        killSwitchActive,
        safetyLatchActive,
        reconcileOk,
        t,
      })
    : null;

  return (
    <div className="panel">
      <h2>{t("console.executionSafetyPanel.title")}</h2>
      <p className="muted small">{t("console.executionSafetyPanel.lead")}</p>
      <ul className="news-list">
        {ACTION_SPECS.map((action) => {
          const reason = actionDisabledReason({
            action,
            killSwitchActive,
            safetyLatchActive,
            reconcileOk,
            t,
          });
          const disabled = Boolean(reason);
          return (
            <li key={action.id}>
              <button
                type="button"
                className={
                  action.dangerous ? "public-btn danger" : "public-btn ghost"
                }
                onClick={() => {
                  setSelected(action.id);
                  setConfirmed(false);
                }}
              >
                {t(action.titleKey)}
              </button>
              <span className="muted small">
                {" "}
                — {disabled ? reason : t("console.safetyCommandActions.select")}
              </span>
            </li>
          );
        })}
      </ul>
      {selectedAction ? (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h3>{t(selectedAction.titleKey)}</h3>
          <label className="muted small">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />{" "}
            {t("console.executionSafetyPanel.confirmCheckbox")}
          </label>
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="public-btn danger"
              disabled={!confirmed || Boolean(disabledReason)}
              aria-disabled={!confirmed || Boolean(disabledReason)}
            >
              {t("console.executionSafetyPanel.executeDisabled")}
            </button>
          </div>
          {disabledReason ? (
            <p className="muted small">{disabledReason}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
