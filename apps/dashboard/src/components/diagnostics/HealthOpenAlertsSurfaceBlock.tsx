"use client";

import { useMemo } from "react";

import { SurfaceDiagnosticCard } from "@/components/diagnostics/SurfaceDiagnosticCard";
import {
  resolveOpenAlertsEscalationSurfaceDiagnostic,
  type OpenAlertLite,
} from "@/lib/surface-diagnostic-catalog";

type Props = Readonly<{
  alerts: readonly OpenAlertLite[];
}>;

export function HealthOpenAlertsSurfaceBlock({ alerts }: Props) {
  const model = useMemo(
    () => resolveOpenAlertsEscalationSurfaceDiagnostic(alerts),
    [alerts],
  );
  if (!model) return null;
  return <SurfaceDiagnosticCard model={model} showSafetyAi />;
}
