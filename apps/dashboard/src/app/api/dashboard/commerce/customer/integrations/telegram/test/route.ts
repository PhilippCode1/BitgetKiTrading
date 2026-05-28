import { NextResponse } from "next/server";

import { requirePortalGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function POST(req: Request) {
  const auth = requirePortalGatewayAuth(req.headers);
  if (!auth.ok) return auth.response;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/integrations/telegram/test",
      auth.authorization,
      { method: "POST", timeoutMs: 15_000 },
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
