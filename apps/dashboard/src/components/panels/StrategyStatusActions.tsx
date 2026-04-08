"use client";

import { useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { publicEnv } from "@/lib/env";
import { strategyLifecycleConfirmMessage } from "@/lib/sensitive-action-prompts";

type Props = Readonly<{
  strategyId: string;
  /** Server-seitig gesetzt: false wenn kein gueltiger Gateway-Admin-Pfad. */
  allowMutations?: boolean;
}>;

export function StrategyStatusActions({
  strategyId,
  allowMutations = true,
}: Props) {
  const { t } = useI18n();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!publicEnv.enableAdmin) {
    return <p className="muted">{t("strategyStatus.disabledEnv")}</p>;
  }

  if (!allowMutations) {
    return (
      <div className="panel">
        <h2>{t("strategyStatus.panelTitle")}</h2>
        <p className="muted degradation-inline">
          {t("strategyStatus.disabledGateway")}
        </p>
      </div>
    );
  }

  async function postStatus(newStatus: string) {
    if (
      typeof window !== "undefined" &&
      !window.confirm(strategyLifecycleConfirmMessage(newStatus))
    ) {
      return;
    }
    setBusy(true);
    setMsg(null);
    setErr(null);
    const res = await fetch("/api/dashboard/admin/strategy-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy_id: strategyId,
        new_status: newStatus,
        reason: "dashboard",
        changed_by: "dashboard-ui",
      }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr(t("strategyStatus.errHttp", { status: res.status }));
      return;
    }
    setMsg(t("strategyStatus.msgStatusSet", { status: newStatus }));
  }

  return (
    <div className="panel">
      <h2>{t("strategyStatus.panelTitle")}</h2>
      <p className="muted">{t("strategyStatus.hintProxy")}</p>
      <div className="btn-row">
        <button
          type="button"
          disabled={busy}
          onClick={() => void postStatus("promoted")}
        >
          {t("strategyStatus.actionPromote")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void postStatus("candidate")}
        >
          {t("strategyStatus.actionCandidate")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void postStatus("shadow")}
        >
          {t("strategyStatus.actionShadow")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void postStatus("retired")}
        >
          {t("strategyStatus.actionRetire")}
        </button>
      </div>
      {msg ? <p className="msg-ok">{msg}</p> : null}
      {err ? <p className="msg-err">{err}</p> : null}
    </div>
  );
}
