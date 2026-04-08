import { NextResponse } from "next/server";

import {
  DashboardBffErrorCode,
  jsonDashboardBffError,
} from "@/lib/gateway-bff-errors";
import { serverEnv } from "@/lib/server-env";

export function gatewayBaseUrl(): string {
  return serverEnv.apiGatewayUrl.replace(/\/$/, "");
}

/**
 * Wenn `fetch()` zum API-Gateway fehlschlaegt (ECONNREFUSED, Timeout, DNS): strukturierte Antwort.
 * Kein 503 bei fehlendem JWT — das liefert nur `requireOperatorGatewayAuth` (praezise Diagnose).
 */
export function upstreamFetchFailedResponse(error: unknown): NextResponse {
  const base = serverEnv.apiGatewayUrl.trim();
  const baseLabel =
    base ||
    "API_GATEWAY_URL nicht gesetzt (ausserhalb development/test Pflicht)";
  const reason =
    error instanceof Error && error.message
      ? error.message
      : typeof error === "string"
        ? error
        : "unbekannter Fehler";
  if (!base) {
    return jsonDashboardBffError(
      503,
      DashboardBffErrorCode.API_GATEWAY_URL_MISSING,
      "API_GATEWAY_URL fehlt auf dem Next-Server — kein Ziel fuer den BFF-Gateway-Proxy. " +
        "Setzen und Next neu starten (siehe docs/LOCAL_START_MINIMUM.md).",
    );
  }
  return jsonDashboardBffError(
    502,
    DashboardBffErrorCode.GATEWAY_TRANSPORT_FAILED,
    `API-Gateway nicht erreichbar (${baseLabel}): ${reason}. ` +
      `Stack: pnpm stack:local oder powershell -File scripts/start_local.ps1. ` +
      `Diagnose: pnpm stack:check. In Staging/Prod: API_GATEWAY_URL pruefen (Host vs. Container).`,
  );
}
