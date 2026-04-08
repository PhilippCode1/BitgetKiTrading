"use client";

import { SafetyDiagnosisInline } from "@/components/diagnostics/SafetyDiagnosisInline";
import { SituationAiExplainPanel } from "@/components/diagnostics/SituationAiExplainPanel";
import { useI18n } from "@/components/i18n/I18nProvider";
import type { SurfaceDiagnosticModel } from "@/lib/surface-diagnostic-catalog";

const CAUSE_IX = [1, 2, 3, 4] as const;
const STEP_IX = [1, 2, 3, 4] as const;

type Props = Readonly<{
  model: SurfaceDiagnosticModel;
  showSafetyAi?: boolean;
  /** Optional: Zusatzzeile (z. B. Hinweis, dass die Sicherheits-KI weiter unten steht). */
  footnoteKey?: string;
}>;

export function SurfaceDiagnosticCard({
  model,
  showSafetyAi = true,
  footnoteKey,
}: Props) {
  const { t } = useI18n();
  const base = model.messageBaseKey;
  const suggestedQ = t(`${base}.suggestedSafetyQuestion`);
  const title = t(`${base}.title`);
  return (
    <div
      className="surface-diagnostic-card warn-banner"
      role="region"
      aria-label={title}
      style={{ marginTop: "0.75rem" }}
    >
      <h3
        className="surface-diagnostic-card__title"
        style={{ margin: "0 0 0.35rem" }}
      >
        {title}
      </h3>
      <p className="muted small" style={{ marginTop: 0 }}>
        {t(`${base}.lead`)}
      </p>
      <h4
        className="surface-diagnostic-card__h muted small"
        style={{ margin: "0.65rem 0 0.25rem", fontWeight: 700 }}
      >
        {t("diagnostic.surfaces.common.sectionCauses")}
      </h4>
      <ul
        className="surface-diagnostic-card__ul"
        style={{ margin: 0, paddingLeft: "1.2rem" }}
      >
        {CAUSE_IX.map((i) => (
          <li key={i} className="small">
            {t(`${base}.cause${i}`)}
          </li>
        ))}
      </ul>
      <h4
        className="surface-diagnostic-card__h muted small"
        style={{ margin: "0.65rem 0 0.25rem", fontWeight: 700 }}
      >
        {t("diagnostic.surfaces.common.sectionServices")}
      </h4>
      <p className="muted small" style={{ marginTop: 0 }}>
        {t(`${base}.services`)}
      </p>
      <h4
        className="surface-diagnostic-card__h muted small"
        style={{ margin: "0.65rem 0 0.25rem", fontWeight: 700 }}
      >
        {t("diagnostic.surfaces.common.sectionInterfaces")}
      </h4>
      <p className="muted small" style={{ marginTop: 0 }}>
        {t(`${base}.interfaces`)}
      </p>
      <h4
        className="surface-diagnostic-card__h muted small"
        style={{ margin: "0.65rem 0 0.25rem", fontWeight: 700 }}
      >
        {t("diagnostic.surfaces.common.sectionNext")}
      </h4>
      <ul
        className="surface-diagnostic-card__ul"
        style={{ margin: 0, paddingLeft: "1.2rem" }}
      >
        {STEP_IX.map((i) => (
          <li key={i} className="small">
            {t(`${base}.step${i}`)}
          </li>
        ))}
      </ul>
      <p className="muted small" style={{ marginTop: "0.65rem" }}>
        {t("diagnostic.surfaces.common.refDocLine")}
      </p>
      {footnoteKey ? (
        <p className="muted small" style={{ marginTop: 6 }}>
          {t(footnoteKey)}
        </p>
      ) : null}
      <SituationAiExplainPanel
        variant="surface"
        model={model}
        title={title}
        lead={t(`${base}.lead`)}
      />
      {showSafetyAi && suggestedQ.length >= 3 ? (
        <SafetyDiagnosisInline
          contextOverlay={model.contextOverlay}
          suggestedSafetyQuestionDe={suggestedQ}
        />
      ) : null}
    </div>
  );
}
