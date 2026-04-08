/** Lesbare JSON-Ausgabe für Operator-Panels (keine Secrets — nur Serverpayload). */
export function prettyJsonLine(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function recordHasKeys(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object")
    return Object.keys(value as Record<string, unknown>).length > 0;
  return true;
}

export function orderStatusCountsNonEmpty(
  counts: Record<string, number> | null | undefined,
): boolean {
  if (!counts || typeof counts !== "object") return false;
  return Object.keys(counts).length > 0;
}
