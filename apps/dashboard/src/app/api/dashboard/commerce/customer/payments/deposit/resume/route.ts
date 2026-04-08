import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const body = await req.text();
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/payments/deposit/resume",
      auth.authorization,
      {
        method: "POST",
        body,
        extraHeaders: { "Content-Type": "application/json" },
        timeoutMs: 20_000,
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
