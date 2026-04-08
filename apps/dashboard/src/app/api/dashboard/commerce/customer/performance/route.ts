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
  for (const k of ["trades_limit", "symbol"] as const) {
    const v = incoming.searchParams.get(k);
    if (v) sp.set(k, v);
  }
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/performance",
      auth.authorization,
      {
        searchParams: sp,
        timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
      },
    );
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const text = await res.text();
  const ct = res.headers.get("content-type") ?? "application/json";
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": ct },
  });
}
