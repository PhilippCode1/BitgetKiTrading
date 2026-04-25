import { NextResponse } from "next/server";

import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";

/**
 * BFF-JSON (read-only) fuer Diagnose, Tests und eventuelle Client-Extensions.
 * Enthaelt keinen Browser-Secret-Header; Aggregation nur serverseitig.
 */
export async function GET() {
  const s = await getCustomerPortalSummary();
  return NextResponse.json(s, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}
