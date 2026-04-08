import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const incoming = new URL(req.url);
  const sp = new URLSearchParams();
  sp.set("format", incoming.searchParams.get("format") || "csv");
  const tl = incoming.searchParams.get("trades_limit");
  if (tl) sp.set("trades_limit", tl);
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/performance/export",
      auth.authorization,
      {
        searchParams: sp,
        timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
      },
    );
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const buf = await res.arrayBuffer();
  const headers = new Headers();
  const ct = res.headers.get("content-type") ?? "text/csv; charset=utf-8";
  headers.set("Content-Type", ct);
  const cd = res.headers.get("content-disposition");
  if (cd) headers.set("Content-Disposition", cd);
  return new NextResponse(buf, { status: res.status, headers });
}
