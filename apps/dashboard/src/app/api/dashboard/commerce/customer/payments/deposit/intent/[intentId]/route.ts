import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

type Params = Readonly<{ params: Promise<{ intentId: string }> }>;

export async function GET(_req: Request, { params }: Params) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const { intentId } = await params;
  const enc = encodeURIComponent(intentId);
  const path = `/v1/commerce/customer/payments/deposit/intents/${enc}`;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(path, auth.authorization, {
      timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
    });
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
