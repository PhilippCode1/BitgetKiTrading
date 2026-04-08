import { NextResponse } from "next/server";

import { serverEnv } from "@/lib/server-env";

/**
 * Liveness: keine Netzwerkaufrufe. `gatewayEnv` zeigt nur, ob Server-ENV gesetzt ist
 * (Wahrheit = Konfiguration, nicht Erreichbarkeit — dafuer GET /api/ready und edge-status).
 */
export function GET() {
  const apiGatewayUrlConfigured = Boolean(serverEnv.apiGatewayUrl.trim());
  const dashboardAuthorizationConfigured = Boolean(
    serverEnv.gatewayAuthorizationHeader,
  );
  return NextResponse.json({
    status: "ok",
    service: "dashboard",
    gatewayEnv: {
      apiGatewayUrlConfigured,
      dashboardAuthorizationConfigured,
    },
  });
}
