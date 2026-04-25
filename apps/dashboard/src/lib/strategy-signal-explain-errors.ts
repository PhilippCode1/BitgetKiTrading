/**
 * Erfolgs-Check fuer Strategie-Signal-Erklaerung.
 * HTTP-Fehler: dieselbe Abbildung wie Operator Explain ({@link resolveOperatorExplainFailure}).
 */

export {
  resolveNetworkFailure,
  sanitizePublicErrorMessage,
  resolveOperatorExplainFailure as resolveStrategySignalExplainFailure,
} from "@/lib/operator-explain-errors";

export function isStrategySignalExplainSuccessPayload(
  parsed: unknown,
): parsed is {
  result: { strategy_explanation_de?: string; execution_authority?: string };
  ok?: boolean;
} {
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return false;
  }
  const p = parsed as Record<string, unknown>;
  if (p.ok === false) {
    return false;
  }
  const r = p.result;
  if (r === null || typeof r !== "object" || Array.isArray(r)) {
    return false;
  }
  const authority = (r as Record<string, unknown>).execution_authority;
  return authority == null || authority === "none";
}
