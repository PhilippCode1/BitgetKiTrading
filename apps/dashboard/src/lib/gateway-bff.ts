import { NextResponse } from "next/server";

import {
  DashboardBffErrorCode,
  jsonDashboardBffError,
} from "@/lib/gateway-bff-errors";
import { gatewayBaseUrl } from "@/lib/gateway-upstream";
import { serverEnv } from "@/lib/server-env";

export type OperatorGatewayAuth =
  | { ok: true; authorization: string }
  | { ok: false; response: NextResponse };

/**
 * Server-only: Bearer/JWT fuer Dashboard-BFF → API-Gateway (`DASHBOARD_GATEWAY_AUTHORIZATION`).
 *
 * Das ist **keine** Endnutzer-Session: derselbe serverseitige Credential wird fuer alle
 * BFF-Aufrufe genutzt. Feingranulare Berechtigung liegt am Gateway (JWT-Claims, Route-Auth).
 * Der Browser sieht diesen Header nicht.
 *
 * Erzeugung (lokal): `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`
 */
export function requireOperatorGatewayAuth(): OperatorGatewayAuth {
  const authorization = serverEnv.gatewayAuthorizationHeader;
  if (!authorization) {
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
  return { ok: true, authorization };
}

/** Vollstaendige URL zum Gateway (path mit oder ohne fuehrendes /). */
export function gatewayAbsoluteUrl(path: string): string {
  const base = gatewayBaseUrl().replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}
