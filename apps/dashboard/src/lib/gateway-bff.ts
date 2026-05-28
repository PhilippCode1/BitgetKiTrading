import "server-only";

import { NextResponse } from "next/server";

import {
  DashboardBffErrorCode,
  jsonDashboardBffError,
} from "@/lib/gateway-bff-errors";
import { gatewayBaseUrl } from "@/lib/gateway-upstream";
import { readPortalAuthorizationFromHeaders } from "@/lib/portal-jwt-server";
import { serverEnv } from "@/lib/server-env";

export type OperatorGatewayAuth =
  | { ok: true; authorization: string; source: "portal_jwt" | "bff_env" }
  | { ok: false; response: NextResponse };

/**
 * Server-only: liefert den Authorization-Header fuer den BFF -> Gateway-Aufruf.
 *
 * Reihenfolge (Least Privilege):
 *  1. Sitzungsbezogenes Portal-JWT aus dem Request-Cookie (`bitget_portal_jwt`).
 *     Dies traegt die Identitaet des Endnutzers (tenant_id, portal_roles).
 *  2. Fallback `DASHBOARD_GATEWAY_AUTHORIZATION` — globaler BFF-Service-Token,
 *     z. B. fuer System-Heartbeats / unauthentifizierte oeffentliche Reads.
 *
 * Kein eigenes Cookie-String-Parsing in Aufrufer-Code — alles laeuft ueber
 * {@link readPortalAuthorizationFromHeaders}.
 */
export function requireOperatorGatewayAuth(
  headersSource?: Headers | null,
): OperatorGatewayAuth {
  const fromCookie = readPortalAuthorizationFromHeaders(headersSource ?? null);
  if (fromCookie) {
    return { ok: true, authorization: fromCookie, source: "portal_jwt" };
  }
  const fallback = (serverEnv.gatewayAuthorizationHeader ?? "").trim();
  if (!fallback) {
    return {
      ok: false,
      response: jsonDashboardBffError(
        503,
        DashboardBffErrorCode.DASHBOARD_GATEWAY_AUTH_MISSING,
        "DASHBOARD_GATEWAY_AUTHORIZATION fehlt — Bearer-JWT (gateway:read) in der " +
          "Dashboard-ENV. Erzeugen: python scripts/mint_dashboard_gateway_jwt.py " +
          "--env-file .env.local --update-env-file; Dashboard neu starten.",
      ),
    };
  }
  return { ok: true, authorization: fallback, source: "bff_env" };
}

/**
 * Kunden-BFF: nur Portal-Session (Cookie `bitget_portal_jwt`).
 * Kein DASHBOARD_GATEWAY_AUTHORIZATION-Fallback — tenant-spezifische Reads/Mutations.
 */
export function requirePortalGatewayAuth(
  headersSource?: Headers | null,
): OperatorGatewayAuth {
  const fromCookie = readPortalAuthorizationFromHeaders(headersSource ?? null);
  if (!fromCookie) {
    return {
      ok: false,
      response: NextResponse.json(
        {
          detail:
            "PORTAL_SESSION_REQUIRED — sign in to the customer portal (bitget_portal_jwt cookie).",
          code: "PORTAL_SESSION_REQUIRED",
          layer: "dashboard-bff",
        },
        { status: 401 },
      ),
    };
  }
  return { ok: true, authorization: fromCookie, source: "portal_jwt" };
}

/** Vollstaendige URL zum Gateway (path mit oder ohne fuehrendes /). */
export function gatewayAbsoluteUrl(path: string): string {
  const base = gatewayBaseUrl().replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}
