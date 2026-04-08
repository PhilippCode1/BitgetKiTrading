"use client";

import { useMemo } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { SafetyDiagnosisPanel } from "@/components/panels/SafetyDiagnosisPanel";

type Props = Readonly<{
  contextOverlay: Record<string, unknown>;
  suggestedSafetyQuestionDe: string;
}>;

/**
 * Kompakte Sicherheits-KI unter einer Oberflächen-Diagnose (Prompt 38).
 * Nutzt einen schlanken Kontext plus Overlay; kein Ersatz für die vollständige Health-Sicherheitskarte.
 */
export function SafetyDiagnosisInline({
  contextOverlay,
  suggestedSafetyQuestionDe,
}: Props) {
  const { t } = useI18n();
  const bundled = useMemo<Record<string, unknown>>(
    () => ({
      context_kind: "safety_diagnostic_v1_surface_inline",
      surface_inline: true,
      ...contextOverlay,
    }),
    [contextOverlay],
  );
  return (
    <details
      className="surface-diagnostic-safety-inline"
      style={{ marginTop: "0.75rem" }}
    >
      <summary
        className="muted small"
        style={{ cursor: "pointer", fontWeight: 600 }}
      >
        {t("diagnostic.surfaces.common.safetyAiToggle")}
      </summary>
      <p className="muted small" style={{ marginTop: 8 }}>
        {t("diagnostic.surfaces.common.safetyAiLead")}
      </p>
      <SafetyDiagnosisPanel
        bundledContextJson={bundled}
        initialQuestionDe={suggestedSafetyQuestionDe}
        embedded
      />
    </details>
  );
}
