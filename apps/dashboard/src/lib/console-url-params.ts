/**
 * Gemeinsame URL-Parameter-Hilfen fuer Operator-Konsolen-Seiten (Signal Center, Cockpit, …).
 * Erste Query-Werte: {@link firstSearchParam} in `console-params.ts`.
 */

/**
 * Baut Query-Strings: leere / null / undefined Werte werden ausgelassen.
 */
export function mergeConsoleSearchParams(
  base: Record<string, string | undefined>,
  extra: Record<string, string | undefined | null>,
): URLSearchParams {
  const u = new URLSearchParams();
  const merged = { ...base, ...extra };
  for (const [k, v] of Object.entries(merged)) {
    if (v === undefined || v === null || v === "") continue;
    u.set(k, v);
  }
  return u;
}

export function consoleHref(
  pathname: string,
  base: Record<string, string | undefined>,
  extra: Record<string, string | undefined | null>,
): string {
  const q = mergeConsoleSearchParams(base, extra).toString();
  return q ? `${pathname}?${q}` : pathname;
}

/** Nur definierte, nicht-leere String-Werte (fuer Chart-URL-Parameter). */
export function pickTruthyQueryFields(
  input: Record<string, string | undefined>,
): Record<string, string> {
  const o: Record<string, string> = {};
  for (const [k, v] of Object.entries(input)) {
    if (typeof v === "string" && v.length > 0) {
      o[k] = v;
    }
  }
  return o;
}
