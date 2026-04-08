"use client";

import { Suspense } from "react";

import { ConsoleFetchNoticeActions } from "@/components/console/ConsoleFetchNoticeActions";
import { SystemCommsPhaseStrip } from "@/components/system-comms/SystemCommsPhaseStrip";
import { useI18n } from "@/components/i18n/I18nProvider";
import { ContentPanel } from "@/components/ui/ContentPanel";
import type { SystemCommsPhase } from "@/lib/system-communication";

type Props = Readonly<{
  titleKey: string;
  bodyKey: string;
  /** Optionale nummerierte naechste Schritte */
  stepKeys?: readonly string[];
  /** Schnellaktionen (Reload, Health, Verbindung, Diagnose) bei leerer Liste nach API-Fehler o.ä. */
  showActions?: boolean;
  /** System-Kommunikationsphase für eine kurze Kontextzeile (z. B. partial, unstable) */
  commsPhase?: SystemCommsPhase;
}>;

/**
 * Leerzustand mit freundlicher Erklaerung und optionalen naechsten Schritten.
 */
export function EmptyStateHelp({
  titleKey,
  bodyKey,
  stepKeys,
  showActions,
  commsPhase,
}: Props) {
  const { t } = useI18n();
  return (
    <ContentPanel className="empty-state-help" role="status">
      {commsPhase ? <SystemCommsPhaseStrip phase={commsPhase} /> : null}
      <h3 className="empty-state-help-title">{t(titleKey)}</h3>
      <p className="muted empty-state-help-body">{t(bodyKey)}</p>
      {stepKeys && stepKeys.length > 0 ? (
        <div>
          <p className="empty-state-help-steps-label muted small">
            {t("help.nextSteps")}
          </p>
          <ol className="empty-state-help-steps">
            {stepKeys.map((k) => (
              <li key={k}>{t(k)}</li>
            ))}
          </ol>
        </div>
      ) : null}
      {showActions ? (
        <div className="empty-state-help-actions">
          <Suspense fallback={null}>
            <ConsoleFetchNoticeActions />
          </Suspense>
        </div>
      ) : null}
    </ContentPanel>
  );
}
