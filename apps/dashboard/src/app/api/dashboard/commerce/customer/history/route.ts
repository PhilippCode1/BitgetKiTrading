import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function GET(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const incoming = new URL(req.url);
  const sp = new URLSearchParams();
  const ledger = incoming.searchParams.get("ledger_limit");
  const audit = incoming.searchParams.get("audit_limit");
  if (ledger) sp.set("ledger_limit", ledger);
  if (audit) sp.set("audit_limit", audit);
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/history",
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
