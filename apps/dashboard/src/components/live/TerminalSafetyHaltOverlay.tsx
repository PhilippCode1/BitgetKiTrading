"use client";

import { useQuery } from "@tanstack/react-query";

import { useI18n } from "@/components/i18n/I18nProvider";
import { fetchSystemHealth } from "@/lib/api";
import {
  isLiveBrokerGlobalHaltFromHealth,
  SYSTEM_HEALTH_QUERY_KEY,
} from "@/lib/live-broker-console";

/**
 * Wenn `ops.live_broker.safety_latch_active` (Global Halt) — blockiert Interaktionen im Live-Terminal.
 */
export function TerminalSafetyHaltOverlay() {
  const { t } = useI18n();
  const { data: health } = useQuery({
    queryKey: [...SYSTEM_HEALTH_QUERY_KEY],
    queryFn: fetchSystemHealth,
    staleTime: 8_000,
    refetchInterval: 10_000,
  });
  if (!isLiveBrokerGlobalHaltFromHealth(health)) {
    return null;
  }
  return (
    <div
      className="live-terminal--halt"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="live-terminal-halt-title"
    >
      <div className="live-terminal--halt__curtain" tabIndex={-1} />
      <div className="live-terminal--halt__card">
        <p id="live-terminal-halt-title" className="live-terminal--halt__title">
          {t("live.terminal.safetyHaltTitle")}
        </p>
        <p className="muted small live-terminal--halt__body">
          {t("live.terminal.safetyHaltBody")}
        </p>
      </div>
    </div>
  );
}
