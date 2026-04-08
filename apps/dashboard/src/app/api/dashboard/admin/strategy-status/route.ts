import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { detail: "ungueltiger JSON-Body" },
      { status: 400 },
    );
  }
  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/admin/strategy-status",
      auth.authorization,
      {
        method: "POST",
        body: JSON.stringify(body),
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
