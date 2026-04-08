import { NextResponse } from "next/server";

import { runGatewayBootstrapProbe } from "@/lib/gateway-bootstrap-probe";
import { serverEnv } from "@/lib/server-env";

export const dynamic = "force-dynamic";

/**
 * Readiness: aktive Pruefung gegen API-Gateway (/health, /ready, Operator-JWT).
 * HTTP 503 wenn Dashboard keine belastbaren /v1-Lesevorgaenge starten sollte.
 */
export async function GET() {
  const probe = await runGatewayBootstrapProbe();
  const ready = probe.rootCause === "ok";
  const payload = {
    ready,
    service: "dashboard",
    rootCause: probe.rootCause,
    detail: probe.rootCause === "ok" ? null : probe.detail,
    gatewayHealthHttpStatus: probe.gatewayHealthHttpStatus,
    gatewayReady: probe.gatewayReadyFlag,
    gatewayReadySummary: probe.gatewayReadySummary,
    operatorHealthHttpStatus: probe.operatorHealthHttpStatus,
    apiGatewayUrl: serverEnv.apiGatewayUrl,
    gatewayAuthorizationConfigured: Boolean(
      serverEnv.gatewayAuthorizationHeader,
    ),
  };
  return NextResponse.json(payload, { status: ready ? 200 : 503 });
}
