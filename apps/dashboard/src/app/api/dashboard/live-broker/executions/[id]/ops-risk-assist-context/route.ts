import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 60_000;

export async function GET(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const { id: executionId } = await ctx.params;
  const t = (executionId ?? "").trim();
  if (!/^[0-9a-f-]{36}$/i.test(t)) {
    return NextResponse.json(
      { detail: "Invalid execution_id (UUID expected)." },
      { status: 400 },
    );
  }

  const traceHeaders = new Headers();
  applyGatewayTraceHeaders(traceHeaders, req.headers);

  const upstreamPath = `/v1/live-broker/executions/${t}/ops-risk-assist-context`;
  try {
    const res = await fetchGatewayUpstream(upstreamPath, auth.authorization, {
      method: "GET",
      extraHeaders: traceHeaders,
      traceSource: req.headers,
      timeoutMs: UPSTREAM_TIMEOUT_MS,
    });
    const text = await res.text();
    const ct = res.headers.get("content-type") ?? "application/json";
    return new NextResponse(text, { status: res.status, headers: { "Content-Type": ct } });
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
}
