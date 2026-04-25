export function isSafetyDiagnosisSuccessPayload(parsed: unknown): boolean {
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return false;
  }
  const env = parsed as { ok?: unknown; result?: unknown };
  if (env.ok !== true) return false;
  const r = env.result;
  if (r === null || typeof r !== "object" || Array.isArray(r)) return false;
  const o = r as Record<string, unknown>;
  return (
    typeof o.incident_summary_de === "string" &&
    o.incident_summary_de.trim().length > 0 &&
    o.execution_authority === "none"
  );
}
