import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

/**
 * Proxied SSE: Browser verbindet same-origin zu Next; Server haengt Authorization ans Gateway.
 */
export async function GET(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const incoming = new URL(req.url);

  let res: Response;
  try {
    const streamHeaders = new Headers({ Accept: "text/event-stream" });
    res = await fetchGatewayUpstream("/v1/live/stream", auth.authorization, {
      searchParams: incoming.searchParams,
      extraHeaders: streamHeaders,
      traceSource: req.headers,
      timeoutMs: null,
      /** Tab/Navigation weg: Upstream sofort beenden, kein hängendes Proxy-SSE. */
      abortSignal: req.signal,
    });
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }

  if (!res.ok) {
    const text = await res.text();
    console.error("[dashboard-bff] live/stream upstream rejected", {
      status: res.status,
      snippet: text.slice(0, 400),
    });
    const ct = res.headers.get("content-type") ?? "application/json";
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": ct },
    });
  }

  const out = new Headers({
    "Content-Type": res.headers.get("content-type") ?? "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  const xr = res.headers.get("x-request-id")?.trim();
  const xc = res.headers.get("x-correlation-id")?.trim();
  if (xr) out.set("X-Request-ID", xr);
  if (xc) out.set("X-Correlation-ID", xc);

  return new NextResponse(res.body, {
    status: 200,
    headers: out,
  });
}
