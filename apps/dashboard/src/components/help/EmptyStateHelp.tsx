"use client";

import { EmptyState } from "@/components/ui/EmptyState";
import type { SystemCommsPhase } from "@/lib/system-communication";

type Props = Readonly<{
  titleKey: string;
  bodyKey: string;
  /** Optionale nummerierte nächste Schritte */
  stepKeys?: readonly string[];
  /** Schnellaktionen (Reload, Health, Verbindung, Diagnose) bei leerer Liste nach API-Fehler o.ä. */
  showActions?: boolean;
  /** System-Kommunikationsphase für eine kurze Kontextzeile (z. B. partial, unstable) */
  commsPhase?: SystemCommsPhase;
}>;

/**
 * Leerzustand mit freundlicher Erklärung und optionalen nächsten Schritten.
 * (Wrapper um {@link EmptyState} — gleiche Inhalte, konsistente Darstellung.)
 */
export function EmptyStateHelp({
  titleKey,
  bodyKey,
  stepKeys,
  showActions,
  commsPhase,
}: Props) {
  return (
    <EmptyState
      className="empty-state-help"
      icon="layers"
      titleKey={titleKey}
      descriptionKey={bodyKey}
      stepKeys={stepKeys}
      showActions={showActions}
      commsPhase={commsPhase}
    />
  );
}
