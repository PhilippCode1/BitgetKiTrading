/**
 * Lesbare Zeilen aus reasons_json (Explain-Payload) — rein zur Anzeige, keine Logikänderung.
 */

export function summarizeReasonsJsonForUi(
  value: unknown,
  maxItems = 32,
): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    const out: string[] = [];
    for (const item of value.slice(0, maxItems)) {
      if (item == null) continue;
      if (typeof item === "string") {
        out.push(item);
        continue;
      }
      if (typeof item === "object" && !Array.isArray(item)) {
        const o = item as Record<string, unknown>;
        const r = o.reason ?? o.message ?? o.code ?? o.label;
        if (typeof r === "string" && r.trim()) {
          out.push(r.trim());
          continue;
        }
      }
      try {
        out.push(JSON.stringify(item));
      } catch {
        out.push(String(item));
      }
    }
    return out;
  }
  if (typeof value === "object") {
    try {
      return [JSON.stringify(value, null, 2)];
    } catch {
      return [String(value)];
    }
  }
  return [String(value)];
}
