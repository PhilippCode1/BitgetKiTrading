import { NextResponse } from "next/server";

import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { readPortalAuthorizationFromHeaders } from "@/lib/portal-jwt-server";

/**
 * BFF-JSON (read-only) fuer Diagnose, Tests und eventuelle Client-Extensions.
 * Enthaelt keinen Browser-Secret-Header; Aggregation nur serverseitig.
 */
export async function GET(req: Request) {
  if (!readPortalAuthorizationFromHeaders(req.headers)) {
    return NextResponse.json(
      { error: "PORTAL_SESSION_REQUIRED" },
      { status: 401 },
    );
  }
  const s = await getCustomerPortalSummary(req.headers);
  return NextResponse.json(s, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}
