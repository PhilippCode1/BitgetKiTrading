/** URL-Parameter fuer Operator-Konsole (z. B. Diagnosemodus). */

export type ConsoleSearchParams = Record<string, string | string[] | undefined>;

export function firstSearchParam(
  sp: ConsoleSearchParams,
  key: string,
): string | undefined {
  const value = sp[key];
  return Array.isArray(value) ? value[0] : value;
}

/** `?diagnostic=1` — Roh-Fehlermeldungen zu API-Fetches sichtbar machen. */
export function diagnosticFromSearchParams(sp: ConsoleSearchParams): boolean {
  return firstSearchParam(sp, "diagnostic") === "1";
}
