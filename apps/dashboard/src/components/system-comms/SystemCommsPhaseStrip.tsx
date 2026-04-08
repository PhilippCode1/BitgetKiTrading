"use client";

import type { SystemCommsPhase } from "@/lib/system-communication";
import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  phase: SystemCommsPhase;
}>;

/** Eine Zeile Kontext für Leerzustände — ruhig, ohne Doppel-Prosa. */
export function SystemCommsPhaseStrip({ phase }: Props) {
  const { t } = useI18n();
  return (
    <p
      className="system-comms-phase-strip muted small"
      role="status"
      data-phase={phase}
    >
      <span className="system-comms-phase-strip__label">
        {t("systemComms.emptyState.contextLead")}:
      </span>{" "}
      <span className="system-comms-phase-strip__value">
        {t(`systemComms.phaseLabel.${phase}`)}
      </span>
    </p>
  );
}
