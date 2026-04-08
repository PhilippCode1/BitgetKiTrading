/**
 * Grenzen fuer optionalen Readonly-Kontext beim Operator Explain (BFF + UI-Hinweise).
 * Abgestimmt mit Orchestrator-Prompt-Cap (~10k Zeichen Kontext-Text); JSON darf nicht beliebig gross werden.
 */
export const OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES = 24_000;

/** UTF-8-Bytegroesse von JSON.stringify(obj) — fuer BFF-Validierung. */
export function readonlyContextJsonUtf8ByteLength(
  obj: Record<string, unknown>,
): number {
  return new TextEncoder().encode(JSON.stringify(obj)).length;
}

/** Max. Zeichen im Kontext-Textfeld (vor JSON.parse) — verhindert Browser-Haenge. */
export const OPERATOR_EXPLAIN_CONTEXT_TEXTAREA_MAX_CHARS = 48_000;
