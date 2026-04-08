import { NextResponse } from "next/server";

import {
  isAssistDashboardSegment,
  isValidAssistConversationId,
} from "@/lib/assist-bff";
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 125_000;

export async function POST(
  req: Request,
  ctx: { params: Promise<{ segment: string }> },
) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const { segment } = await ctx.params;
  if (!isAssistDashboardSegment(segment)) {
    return NextResponse.json(
      { detail: "Unknown assist segment." },
      { status: 404 },
    );
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
  const o = body as Record<string, unknown>;
  const cid = o.conversation_id;
  if (typeof cid !== "string" || !isValidAssistConversationId(cid)) {
    return NextResponse.json(
      {
        detail: {
          code: "ASSIST_CONVERSATION_ID_INVALID",
          message:
            "conversation_id must be a canonical UUID string (36 chars, version/variant valid).",
        },
      },
      { status: 400 },
    );
  }
  const msg = o.user_message_de;
  if (typeof msg !== "string" || msg.trim().length < 3) {
    return NextResponse.json(
      {
        detail: "user_message_de must be a string with at least 3 characters.",
      },
      { status: 400 },
    );
  }
  let context_json: Record<string, unknown> = {};
  const ctxRaw = o.context_json;
  if (ctxRaw !== undefined && ctxRaw !== null) {
    if (typeof ctxRaw !== "object" || Array.isArray(ctxRaw)) {
      return NextResponse.json(
        { detail: "context_json must be a JSON object when provided." },
        { status: 400 },
      );
    }
    context_json = ctxRaw as Record<string, unknown>;
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);
  const traceRid = traceHeaders.get("X-Request-ID")!;
  const traceCid = traceHeaders.get("X-Correlation-ID")!;

  const upstreamPath = `/v1/llm/assist/${segment}/turn`;
  let res: Response;
  try {
    res = await fetchGatewayUpstream(upstreamPath, auth.authorization, {
      method: "POST",
      body: JSON.stringify({
        conversation_id: cid.trim(),
        user_message_de: msg.trim(),
        context_json,
      }),
      extraHeaders: traceHeaders,
      traceSource: req.headers,
      timeoutMs: UPSTREAM_TIMEOUT_MS,
    });
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const text = await res.text();
  const ct = res.headers.get("content-type") ?? "application/json";
  const outHeaders = new Headers({ "Content-Type": ct });
  const xr = res.headers.get("x-request-id")?.trim();
  const xc = res.headers.get("x-correlation-id")?.trim();
  if (xr) outHeaders.set("X-Request-ID", xr);
  else outHeaders.set("X-Request-ID", traceRid);
  if (xc) outHeaders.set("X-Correlation-ID", xc);
  else outHeaders.set("X-Correlation-ID", traceCid);
  return new NextResponse(text, { status: res.status, headers: outHeaders });
}
