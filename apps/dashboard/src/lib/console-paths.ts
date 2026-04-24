/** Basis-Pfad der Operator-Konsole (App Router). */
export const CONSOLE_BASE = "/console";

/** Endkunden-Portal (Modul Mate) — abgeschottet von {@link CONSOLE_BASE}. */
export const PORTAL_BASE = "/portal";

export function portalPath(segment: string): string {
  const s = segment.replace(/^\/+/, "");
  return `${PORTAL_BASE}/${s}`;
}

/** Kunden-Portal: z. B. `billing` -> `/portal/account/billing` */
export function portalAccountPath(segment: string): string {
  const s = segment.replace(/^\/+/, "");
  return `${PORTAL_BASE}/account/${s}`;
}

/** Pfad unterhalb von {@link CONSOLE_BASE}, z. B. `ops` → `/console/ops`. */
export function consolePath(segment: string): string {
  const s = segment.replace(/^\/+/, "");
  return `${CONSOLE_BASE}/${s}`;
}
