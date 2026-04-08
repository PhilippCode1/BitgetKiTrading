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

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body." }, { status: 400 });
  }
  if (body === null || typeof body !== "object") {
    return NextResponse.json(
      { detail: "Body must be a JSON object." },
      { status: 400 },
    );
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      `/v1/operator/ai-strategy-proposal-drafts/${encodeURIComponent(draftId.trim())}/request-promotion`,
      auth.authorization,
      {
        method: "POST",
        body: JSON.stringify(body),
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
