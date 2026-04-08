/**
 * Extrahiert eine lesbare Fehlermeldung aus typischen API-Gateway-/FastAPI-JSON-Antworten.
 */

export function formatApiErrorDetail(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) {
    return "Unbekannter Fehler (leere Antwort).";
  }
  try {
    const j = JSON.parse(trimmed) as Record<string, unknown>;
    const d = j.detail;
    if (typeof d === "string") {
      return d;
    }
    if (d && typeof d === "object" && !Array.isArray(d)) {
      const o = d as Record<string, unknown>;
      const msg = o.message;
      const code = o.code;
      if (typeof msg === "string" && typeof code === "string") {
        return `${code}: ${msg}`;
      }
      if (typeof msg === "string") {
        return msg;
      }
      return JSON.stringify(d).slice(0, 800);
    }
    if (Array.isArray(d) && d.length > 0) {
      return d
        .map((item) =>
          typeof item === "object" ? JSON.stringify(item) : String(item),
        )
        .join("; ")
        .slice(0, 800);
    }
    const err = j.error;
    if (err && typeof err === "object" && !Array.isArray(err)) {
      const m = (err as Record<string, unknown>).message;
      if (typeof m === "string") {
        return m;
      }
    }
    if (typeof j.message === "string") {
      return j.message;
    }
  } catch {
    /* Rohtext */
  }
  return trimmed.slice(0, 800);
}
