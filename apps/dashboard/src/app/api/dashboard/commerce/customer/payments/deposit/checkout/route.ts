import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const idem =
    req.headers.get("idempotency-key")?.trim() ??
    req.headers.get("Idempotency-Key")?.trim();
  if (!idem || idem.length < 8) {
    return NextResponse.json(
      { detail: "Idempotency-Key fehlt oder zu kurz (min. 8)" },
      { status: 400 },
    );
  }
  const body = await req.text();
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/payments/deposit/checkout",
      auth.authorization,
      {
        method: "POST",
        body,
        extraHeaders: {
          "Content-Type": "application/json",
          "Idempotency-Key": idem,
        },
        timeoutMs: 30_000,
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
