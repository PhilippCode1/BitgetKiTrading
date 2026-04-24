/**
 * BFF-Konstanten fuer POST /api/dashboard/llm/assist/[segment]
 * (muss mit Gateway-Pfaden und Orchestrator-Rollen konsistent bleiben).
 */
export const ASSIST_DASHBOARD_SEGMENTS = [
  "admin-operations",
  "strategy-signal",
  "customer-onboarding",
  "support-billing",
  "ops-risk",
] as const;

export type AssistDashboardSegment = (typeof ASSIST_DASHBOARD_SEGMENTS)[number];

export function isAssistDashboardSegment(
  s: string,
): s is AssistDashboardSegment {
  return (ASSIST_DASHBOARD_SEGMENTS as readonly string[]).includes(s);
}

/** RFC-4122 UUID (Groß-/Kleinschreibung egal), exakt 36 Zeichen. */
const ASSIST_CONVERSATION_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isValidAssistConversationId(id: string): boolean {
  const t = id.trim();
  return t.length === 36 && ASSIST_CONVERSATION_UUID_RE.test(t);
}
