import { CONSOLE_BASE } from "@/lib/console-paths";

/** Reine Marketing-/Produkt-Huelle ohne Operator-Shell. */
export const MARKETING_PUBLIC_ROUTES: ReadonlySet<string> = new Set<string>([
  "/",
]);

export function isMarketingPublicRoute(pathname: string): boolean {
  return MARKETING_PUBLIC_ROUTES.has(pathname);
}

/** Pfade, die die Operator-Shell und serverseitige Daten erwarten. */
export function consoleRouteRequiresOperatorShell(pathname: string): boolean {
  return pathname === CONSOLE_BASE || pathname.startsWith(`${CONSOLE_BASE}/`);
}

/** Interne Admin-/Safety-Oberflaeche (weiterhin serverseitig geschuetzt). */
export function isAdminSafetyConsolePath(pathname: string): boolean {
  return (
    pathname === `${CONSOLE_BASE}/admin` ||
    pathname.startsWith(`${CONSOLE_BASE}/admin/`)
  );
}
