/** Basis-Pfad der Operator-Konsole (App Router). */
export const CONSOLE_BASE = "/console";

/** Pfad unterhalb von {@link CONSOLE_BASE}, z. B. `ops` → `/console/ops`. */
export function consolePath(segment: string): string {
  const s = segment.replace(/^\/+/, "");
  return `${CONSOLE_BASE}/${s}`;
}
