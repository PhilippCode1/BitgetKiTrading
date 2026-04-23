/**
 * Erkennung von Roh-JSON / HTML, die als Fehlermeldung oder technischer String
 * in der UI landen, ohne sofort alles in den Nutzerfließtext zu geben.
 */

const JSONISH_START = /^\s*[\[\{]"/;
const JSONISH_LOOSE = /^\s*[\{\[]/;

/**
 * Lange JSON-/HTML-Blöcke, die eher Fehler-Response-Bodies als Kurzmeldung sind.
 */
export function looksLikeRawServerPayloadString(
  s: string,
  minLen = 64,
): boolean {
  const t = s.trim();
  if (t.length < minLen) return false;
  if (JSONISH_LOOSE.test(t) && t.length > minLen) {
    if (t.startsWith("{") || t.startsWith("[")) {
      if (t.length > 200) return true;
    }
  }
  if (JSONISH_START.test(t)) return true;
  if (/^\s*<!doctype html/i.test(t) || t.startsWith("<html")) return true;
  return false;
}

/**
 * Technik-Klappe: Inhalte hübsch machen, wenn es geparst werden kann, sonst kürzen.
 */
export function formatTechnicalDetailForPre(raw: string, max = 6_000): string {
  const t = raw.trim();
  if (!t) return "";
  if (looksLikeRawServerPayloadString(t, 8)) {
    try {
      const p = JSON.parse(t) as unknown;
      if (p !== null && (typeof p === "object" || Array.isArray(p)))
        return JSON.stringify(p, null, 2).slice(0, max);
    } catch {
      /* plain text with braces */
    }
  }
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}
