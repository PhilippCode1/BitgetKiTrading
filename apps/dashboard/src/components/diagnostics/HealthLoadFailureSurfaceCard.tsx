"use client";

import { useMemo } from "react";

import { SurfaceDiagnosticCard } from "@/components/diagnostics/SurfaceDiagnosticCard";
import { resolveHealthPageLoadSurfaceDiagnostic } from "@/lib/surface-diagnostic-catalog";

type Props = Readonly<{
  errorMessage: string;
}>;

export function HealthLoadFailureSurfaceCard({ errorMessage }: Props) {
  const model = useMemo(
    () => resolveHealthPageLoadSurfaceDiagnostic(errorMessage),
    [errorMessage],
  );
  return (
    <SurfaceDiagnosticCard
      model={model}
      showSafetyAi={false}
      footnoteKey="diagnostic.surfaces.healthPageLoadFailed.safetyBelowHint"
    />
  );
}
