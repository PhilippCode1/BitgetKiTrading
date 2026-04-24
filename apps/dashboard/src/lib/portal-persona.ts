import { cookies } from "next/headers";
import type { NextRequest } from "next/server";

import {
  type DashboardPersona,
  resolveDashboardPersonaFromToken,
} from "@/lib/operator-jwt";

/**
 * HttpOnly-Cookie mit dem Mandanten-JWT (HS256, gleiches GATEWAY_JWT_SECRET wie API-Gateway).
 * Setzen bei Login/Session — nicht mit DASHBOARD_GATEWAY_AUTHORIZATION (BFF) verwechseln.
 */
export const PORTAL_JWT_COOKIE_NAME = "bitget_portal_jwt";

/**
 * Claim-basiert: Kunde, wenn `portal_roles` / `platform_role` den Kunden-Portal-Markierung traegt.
 * Ohne Cookie oder bei ungueltigem Token: `unknown` (bisheriges Operator-Standardverhalten).
 */
export async function getDashboardPersonaFromRequest(
  request: NextRequest,
): Promise<DashboardPersona> {
  const raw = request.cookies.get(PORTAL_JWT_COOKIE_NAME)?.value;
  if (!raw?.trim()) {
    return "unknown";
  }
  const secret = (process.env.GATEWAY_JWT_SECRET ?? "").trim() || null;
  return resolveDashboardPersonaFromToken(
    raw.startsWith("Bearer ") ? raw : `Bearer ${raw}`,
    secret,
  );
}

/**
 * Server Components / Layouts: gleiche Persona-Logik wie die Middleware
 * (Cookie `bitget_portal_jwt` + GATEWAY_JWT_SECRET).
 */
export async function getDashboardPersonaForServerComponent(): Promise<DashboardPersona> {
  const jar = await cookies();
  const raw = jar.get(PORTAL_JWT_COOKIE_NAME)?.value;
  if (!raw?.trim()) {
    return "unknown";
  }
  const secret = (process.env.GATEWAY_JWT_SECRET ?? "").trim() || null;
  return resolveDashboardPersonaFromToken(
    raw.startsWith("Bearer ") ? raw : `Bearer ${raw}`,
    secret,
  );
}
