import { NextResponse } from "next/server";

/**
 * Stabile Codes fuer BFF-Clients (ohne Secrets). `layer` markiert die Quelle einheitlich.
 */
export const DashboardBffErrorCode = {
  DASHBOARD_GATEWAY_AUTH_MISSING: "DASHBOARD_GATEWAY_AUTH_MISSING",
  API_GATEWAY_URL_MISSING: "API_GATEWAY_URL_MISSING",
  GATEWAY_TRANSPORT_FAILED: "GATEWAY_TRANSPORT_FAILED",
} as const;

export type DashboardBffErrorCodeValue =
  (typeof DashboardBffErrorCode)[keyof typeof DashboardBffErrorCode];

export function jsonDashboardBffError(
  status: 502 | 503,
  code: DashboardBffErrorCodeValue,
  detail: string,
): NextResponse {
  return NextResponse.json(
    {
      detail,
      code,
      layer: "dashboard-bff",
    },
    { status },
  );
}
