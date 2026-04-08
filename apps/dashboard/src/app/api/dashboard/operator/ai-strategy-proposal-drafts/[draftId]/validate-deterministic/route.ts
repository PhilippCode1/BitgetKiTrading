import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

type P = { draftId: string };

export async function POST(req: Request, context: { params: P | Promise<P> }) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const { draftId } = await Promise.resolve(context.params);
  if (!draftId?.trim()) {
    return NextResponse.json({ detail: "draftId required" }, { status: 400 });
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      `/v1/operator/ai-strategy-proposal-drafts/${encodeURIComponent(draftId.trim())}/validate-deterministic`,
      auth.authorization,
      {
        method: "POST",
        body: "{}",
        extraHeaders: traceHeaders,
        traceSource: req.headers,
        timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS,
      },
    );
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/json",
    },
  });
}
