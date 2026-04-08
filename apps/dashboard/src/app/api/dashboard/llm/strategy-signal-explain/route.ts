import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 125_000;
const FOCUS_MAX_LEN = 8000;
/** Grober Schutz vor extrem grossen Bodies (Gateway/Orchestrator truncaten zusaetzlich). */
const SIGNAL_CONTEXT_JSON_MAX_CHARS = 96_000;

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
  const ctxRaw = (body as { signal_context_json?: unknown })
    .signal_context_json;
  if (ctxRaw !== undefined && ctxRaw !== null) {
    if (typeof ctxRaw !== "object" || Array.isArray(ctxRaw)) {
      return NextResponse.json(
        { detail: "signal_context_json must be a JSON object when provided." },
        { status: 400 },
      );
    }
  }
  const signal_context_json =
    ctxRaw !== undefined &&
    ctxRaw !== null &&
    typeof ctxRaw === "object" &&
    !Array.isArray(ctxRaw)
      ? (ctxRaw as Record<string, unknown>)
      : {};

  let focusRaw = (body as { focus_question_de?: unknown }).focus_question_de;
  let focus_question_de: string | undefined;
  if (focusRaw !== undefined && focusRaw !== null) {
    if (typeof focusRaw !== "string") {
      return NextResponse.json(
        { detail: "focus_question_de must be a string when provided." },
        { status: 400 },
      );
    }
    const ft = focusRaw.trim();
    if (ft.length > FOCUS_MAX_LEN) {
      return NextResponse.json(
        {
          detail: {
            code: "FOCUS_QUESTION_TOO_LONG",
            message: `focus_question_de must be at most ${FOCUS_MAX_LEN} characters.`,
          },
        },
        { status: 400 },
      );
    }
    focus_question_de = ft.length > 0 ? ft : undefined;
  }

  const keyCount = Object.keys(signal_context_json).length;
  const fqLen = (focus_question_de ?? "").length;
  if (keyCount === 0 && fqLen < 3) {
    return NextResponse.json(
      {
        detail: {
          code: "STRATEGY_EXPLAIN_INPUT_REQUIRED",
          message:
            "signal_context_json must be non-empty or focus_question_de must have at least 3 characters.",
        },
      },
      { status: 400 },
    );
  }

  try {
    const ser = JSON.stringify(signal_context_json);
    if (ser.length > SIGNAL_CONTEXT_JSON_MAX_CHARS) {
      return NextResponse.json(
        {
          detail: {
            code: "SIGNAL_CONTEXT_TOO_LARGE",
            message: `signal_context_json serializes to more than ${SIGNAL_CONTEXT_JSON_MAX_CHARS} characters.`,
          },
        },
        { status: 413 },
      );
    }
  } catch {
    return NextResponse.json(
      {
        detail: {
          code: "SIGNAL_CONTEXT_NOT_SERIALIZABLE",
          message: "signal_context_json is not JSON-serializable.",
        },
      },
      { status: 400 },
    );
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);
  const traceRid = traceHeaders.get("X-Request-ID")!;
  const traceCid = traceHeaders.get("X-Correlation-ID")!;

  const payload: Record<string, unknown> = { signal_context_json };
  if (focus_question_de !== undefined) {
    payload.focus_question_de = focus_question_de;
  }

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/llm/operator/strategy-signal-explain",
      auth.authorization,
      {
        method: "POST",
        body: JSON.stringify(payload),
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
