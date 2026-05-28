import { NextResponse } from "next/server";

import { requirePortalGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function GET(req: Request) {
  const auth = requirePortalGatewayAuth(req.headers);
  if (!auth.ok) return auth.response;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/integrations",
      auth.authorization,
      {
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
