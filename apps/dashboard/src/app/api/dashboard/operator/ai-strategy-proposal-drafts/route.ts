import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayTraceHeaders } from "@/lib/gateway-trace-headers";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_DEFAULT_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

const UPSTREAM_TIMEOUT_MS = 128_000;
const CONTEXT_MAX_CHARS = 96_000;
const FOCUS_MAX = 8000;

export async function GET(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const u = new URL(req.url);
  const signalId = u.searchParams.get("signal_id")?.trim() || undefined;
  const limitRaw = u.searchParams.get("limit");
  const limit =
    limitRaw != null && limitRaw !== ""
      ? Math.min(50, Math.max(1, Number(limitRaw) || 20))
      : 20;

  const qs = new URLSearchParams();
  if (signalId) qs.set("signal_id", signalId);
  qs.set("limit", String(limit));

  const traceHeaders = new Headers();
  applyGatewayTraceHeaders(traceHeaders, req.headers);

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      `/v1/operator/ai-strategy-proposal-drafts?${qs.toString()}`,
      auth.authorization,
      {
        method: "GET",
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
  const b = body as Record<string, unknown>;
  const chartRaw = b.chart_context_json;
  if (chartRaw !== undefined && chartRaw !== null) {
    if (typeof chartRaw !== "object" || Array.isArray(chartRaw)) {
      return NextResponse.json(
        { detail: "chart_context_json must be a JSON object when provided." },
        { status: 400 },
      );
    }
  }
  const chart_context_json =
    chartRaw != null && typeof chartRaw === "object" && !Array.isArray(chartRaw)
      ? (chartRaw as Record<string, unknown>)
      : {};

  let focus_question_de: string | undefined;
  const fr = b.focus_question_de;
  if (fr !== undefined && fr !== null) {
    if (typeof fr !== "string") {
      return NextResponse.json(
        { detail: "focus_question_de must be a string when provided." },
        { status: 400 },
      );
    }
    const ft = fr.trim();
    if (ft.length > FOCUS_MAX) {
      return NextResponse.json(
        {
          detail: {
            code: "FOCUS_TOO_LONG",
            message: `focus_question_de must be at most ${FOCUS_MAX} characters.`,
          },
        },
        { status: 400 },
      );
    }
    focus_question_de = ft.length > 0 ? ft : undefined;
  }

  const keyCount = Object.keys(chart_context_json).length;
  const fqLen = (focus_question_de ?? "").length;
  if (keyCount === 0 && fqLen < 3) {
    return NextResponse.json(
      {
        detail: {
          code: "CONTEXT_OR_FOCUS_REQUIRED",
          message:
            "chart_context_json must be non-empty or focus_question_de at least 3 characters.",
        },
      },
      { status: 400 },
    );
  }

  try {
    const ser = JSON.stringify(chart_context_json);
    if (ser.length > CONTEXT_MAX_CHARS) {
      return NextResponse.json(
        {
          detail: {
            code: "CONTEXT_TOO_LARGE",
            message: `chart_context_json serializes to more than ${CONTEXT_MAX_CHARS} characters.`,
          },
        },
        { status: 413 },
      );
    }
  } catch {
    return NextResponse.json(
      {
        detail: {
          code: "CONTEXT_NOT_SERIALIZABLE",
          message: "Not JSON-serializable.",
        },
      },
      { status: 400 },
    );
  }

  const signal_id =
    typeof b.signal_id === "string" && b.signal_id.trim()
      ? b.signal_id.trim().slice(0, 128)
      : undefined;
  const symbol =
    typeof b.symbol === "string" ? b.symbol.trim().slice(0, 64) : "";
  const timeframe =
    typeof b.timeframe === "string" ? b.timeframe.trim().slice(0, 32) : "";

  const payload: Record<string, unknown> = {
    chart_context_json,
    symbol,
    timeframe,
  };
  if (signal_id) payload.signal_id = signal_id;
  if (focus_question_de !== undefined) {
    payload.focus_question_de = focus_question_de;
  }

  const traceHeaders = new Headers({ "Content-Type": "application/json" });
  applyGatewayTraceHeaders(traceHeaders, req.headers);

  let res: Response;
  try {
    res = await fetchGatewayUpstream(
      "/v1/operator/ai-strategy-proposal-drafts/generate-and-store",
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
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/json",
    },
  });
}
