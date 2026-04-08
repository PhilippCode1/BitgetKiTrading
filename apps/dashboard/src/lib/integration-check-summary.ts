import type {
  IntegrationsMatrixBlock,
  IntegrationsMatrixRow,
} from "@/lib/types";

export type IntegrationRollup = Readonly<{
  error: number;
  misconfigured: number;
  degraded: number;
  notConfigured: number;
  disabled: number;
  ok: number;
  total: number;
}>;

const BUCKET: Record<string, keyof IntegrationRollup | null> = {
  error: "error",
  misconfigured: "misconfigured",
  degraded: "degraded",
  not_configured: "notConfigured",
  disabled: "disabled",
  ok: "ok",
};

export function rollupIntegrationMatrix(
  matrix: IntegrationsMatrixBlock | null | undefined,
): IntegrationRollup {
  const empty: IntegrationRollup = {
    error: 0,
    misconfigured: 0,
    degraded: 0,
    notConfigured: 0,
    disabled: 0,
    ok: 0,
    total: 0,
  };
  if (!matrix?.integrations?.length) return empty;
  const r = { ...empty };
  for (const row of matrix.integrations) {
    const key = BUCKET[row.health_status] ?? null;
    if (key) r[key] += 1;
    else r.degraded += 1;
    r.total += 1;
  }
  return r;
}

export function integrationMatrixWorstRows(
  rows: IntegrationsMatrixRow[],
): IntegrationsMatrixRow[] {
  const bad = new Set(["error", "misconfigured", "degraded", "not_configured"]);
  return rows.filter((row) => bad.has(row.health_status));
}
