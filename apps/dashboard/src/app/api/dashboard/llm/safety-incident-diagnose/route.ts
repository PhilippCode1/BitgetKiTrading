import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";
import {
  OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES,
  readonlyContextJsonUtf8ByteLength,
} from "@/lib/operator-explain-context";
import { redactSensitiveDiagnosticBranches } from "@/lib/safety-diagnosis-context";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 125_000;
const QUESTION_MAX_LEN = 8000;

export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

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
  const q = (body as { question_de?: unknown }).question_de;
  if (typeof q !== "string" || q.trim().length < 3) {
    return NextResponse.json(
      { detail: "question_de must be a string with at least 3 characters." },
      { status: 400 },
    );
  }
  const qt = q.trim();
  if (qt.length > QUESTION_MAX_LEN) {
    return NextResponse.json(
      {
        detail: {
          code: "QUESTION_TOO_LONG",
          message: `question_de must be at most ${QUESTION_MAX_LEN} characters.`,
        },
      },
      { status: 400 },
    );
  }
  const ctxRaw = (body as { diagnostic_context_json?: unknown })
    .diagnostic_context_json;
  let diagnostic_context_json: Record<string, unknown> = {};
  if (ctxRaw !== undefined && ctxRaw !== null) {
    if (typeof ctxRaw !== "object" || Array.isArray(ctxRaw)) {
      return NextResponse.json(
        {
          detail:
            "diagnostic_context_json must be a JSON object when provided.",
        },
        { status: 400 },
      );
    }
    diagnostic_context_json = redactSensitiveDiagnosticBranches(
      ctxRaw,
    ) as Record<string, unknown>;
  }

  const ctxBytes = readonlyContextJsonUtf8ByteLength(diagnostic_context_json);
  if (ctxBytes > OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES) {
    return NextResponse.json(
      {
        detail: {
          code: "CONTEXT_JSON_TOO_LARGE",
          message: `diagnostic_context_json exceeds ${OPERATOR_EXPLAIN_CONTEXT_JSON_MAX_BYTES} UTF-8 bytes (${ctxBytes}).`,
        },
      },
      { status: 400 },
    );
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);
  const traceRid = traceHeaders.get("X-Request-ID")!;
  const traceCid = traceHeaders.get("X-Correlation-ID")!;

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/llm/operator/safety-incident-diagnosis",
      auth.authorization,
      {
        method: "POST",
        body: JSON.stringify({ question_de: qt, diagnostic_context_json }),
        extraHeaders: traceHeaders,
        traceSource: req.headers,
        timeoutMs: UPSTREAM_TIMEOUT_MS,
      },
    );
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const text = await res.text();
  const ct = res.headers.get("content-type") ?? "application/json";
  const outHeaders = new Headers({ "Content-Type": ct });
  const xr = res.headers.get("x-request-id")?.trim();
  const xc = res.headers.get("x-correlation-id")?.trim();
  if (xr) {
    outHeaders.set("X-Request-ID", xr);
  } else {
    outHeaders.set("X-Request-ID", traceRid);
  }
  if (xc) {
    outHeaders.set("X-Correlation-ID", xc);
  } else {
    outHeaders.set("X-Correlation-ID", traceCid);
  }
  return new NextResponse(text, { status: res.status, headers: outHeaders });
}
