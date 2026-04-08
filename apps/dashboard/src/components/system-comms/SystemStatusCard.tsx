import type { ReactNode } from "react";

import type { SystemCommsPhase } from "@/lib/system-communication";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

type Props = Readonly<{
  phase: SystemCommsPhase;
  titleKey: string;
  titleVars?: Record<string, string | number | boolean>;
  bodyKey: string;
  bodyVars?: Record<string, string | number | boolean>;
  /** Nummerierte nächste Schritte (i18n-Keys) */
  stepKeys?: readonly string[];
  technical?: string | null;
  /** Rohdaten nur bei Diagnosemodus */
  showTechnical?: boolean;
  diagnosticSummaryLabel?: string;
  t: TranslateFn;
  children?: ReactNode;
}>;

/**
 * Systemstatus-Karte: Phase, verständliche Erklärung, optionale Schritte, Experten-Klappe.
 * Für Health, BFF, Konfiguration und andere zentrale Meldungen.
 */
export function SystemStatusCard({
  phase,
  titleKey,
  titleVars,
  bodyKey,
  bodyVars,
  stepKeys,
  technical,
  showTechnical = false,
  diagnosticSummaryLabel,
  t,
  children,
}: Props) {
  const phaseLabel = t(`systemComms.phaseLabel.${phase}`);
  const stepsLabel = t("systemComms.card.stepsLabel");

  return (
    <article
      className={`system-comms-card system-comms-card--phase-${phase}`}
      role="status"
      aria-label={phaseLabel}
    >
      <div className="system-comms-card__inner">
        <header className="system-comms-card__header">
          <span
            className="system-comms-card__phase-pill"
            data-phase={phase}
          >
            {phaseLabel}
          </span>
          <h3 className="system-comms-card__title">{t(titleKey, titleVars)}</h3>
        </header>
        <p className="system-comms-card__body muted small">{t(bodyKey, bodyVars)}</p>
        {stepKeys && stepKeys.length > 0 ? (
          <div className="system-comms-card__steps">
            <p className="system-comms-card__steps-label muted small">
              {stepsLabel}
            </p>
            <ol className="system-comms-card__steps-list">
              {stepKeys.map((k) => (
                <li key={k}>{t(k)}</li>
              ))}
            </ol>
          </div>
        ) : null}
        {children ? (
          <div className="system-comms-card__children">{children}</div>
        ) : null}
        {showTechnical && technical ? (
          <details className="system-comms-card__expert console-fetch-notice__diag small">
            <summary className="console-fetch-notice__diag-sum">
              {diagnosticSummaryLabel ?? t("systemComms.card.expertDetails")}
            </summary>
            <pre className="console-fetch-notice__pre">{technical}</pre>
          </details>
        ) : null}
      </div>
    </article>
  );
}
