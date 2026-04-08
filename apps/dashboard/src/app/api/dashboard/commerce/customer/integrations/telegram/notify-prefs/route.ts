import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

export async function GET() {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/integrations/telegram/notify-prefs",
      auth.authorization,
      { timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS },
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

export async function PATCH(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const body = await req.text();
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/integrations/telegram/notify-prefs",
      auth.authorization,
      {
        method: "PATCH",
        body: body || "{}",
        timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
        traceSource: req.headers,
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
