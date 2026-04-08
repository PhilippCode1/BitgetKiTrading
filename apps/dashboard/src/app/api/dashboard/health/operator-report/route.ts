import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

/**
 * Proxied PDF: GET /v1/system/health/operator-report.pdf (Gateway, Operator-JWT).
 * Ermoeglicht Download aus dem Browser ohne Client-Secret.
 */
export async function GET() {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/system/health/operator-report.pdf",
      auth.authorization,
      {
        timeoutMs: 120_000,
      },
    );
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  if (!res.ok) {
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "text/plain",
      },
    });
  }
  const buf = await res.arrayBuffer();
  const headers = new Headers();
  headers.set(
    "Content-Type",
    res.headers.get("content-type") ?? "application/pdf",
  );
  const cd = res.headers.get("content-disposition");
  if (cd) {
    headers.set("Content-Disposition", cd);
  }
  headers.set("Cache-Control", "no-store");
  return new NextResponse(buf, { status: 200, headers });
}
