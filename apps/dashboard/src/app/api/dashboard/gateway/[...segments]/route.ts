import { NextResponse } from "next/server";

import { genericGatewayBffAllowsPostPath } from "@/lib/dashboard-bff-allowlists";
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { applyGatewayReadStatusHeaders } from "@/lib/gateway-read-response-headers";
import {
  fetchGatewayGetWithRetry,
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

function gatewayCatchAllUnsupportedMethod(): NextResponse {
  return NextResponse.json(
    {
      detail:
        "Nur GET (generisch unter /v1/*) und POST (nur Vertragsbaum) sind erlaubt.",
    },
    { status: 405, headers: { Allow: "GET, POST" } },
  );
}

/**
 * Generischer GET-Proxy: `/api/dashboard/gateway/v1/...` → Gateway mit serverseitigem BFF-Bearer.
 * Browser nutzt diesen Pfad fuer /v1-JSON statt direktem Gateway (kein Gateway-JWT im Client).
 */
export async function GET(
  req: Request,
  ctx: { params: Promise<{ segments: string[] }> },
) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const { segments } = await ctx.params;
  if (!segments?.length || segments[0] !== "v1") {
    return NextResponse.json(
      { detail: "Nur Pfade unter /v1/* sind erlaubt." },
      { status: 404 },
    );
  }

  const path = `/${segments.join("/")}`;
  const incoming = new URL(req.url);

  let res: Response;
  try {
    res = await fetchGatewayGetWithRetry(path, auth.authorization, {
      searchParams: incoming.searchParams,
      timeoutMs: 60_000,
    });
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/pdf") || ct.includes("octet-stream")) {
    const buf = await res.arrayBuffer();
    const headers = new Headers();
    headers.set("Content-Type", ct || "application/octet-stream");
    const cd = res.headers.get("content-disposition");
    if (cd) {
      headers.set("Content-Disposition", cd);
    }
    headers.set("Cache-Control", "no-store");
    return new NextResponse(buf, { status: res.status, headers });
  }
  const text = await res.text();
  const out = new Headers({
    "Content-Type": ct || "application/json",
  });
  out.set("Cache-Control", "no-store");
  applyGatewayReadStatusHeaders(out, text, ct || "application/json");
  return new NextResponse(text, { status: res.status, headers: out });
}

/**
 * POST nur fuer `/v1/commerce/customer/contracts` und Unterpfade (Vertragsworkflow).
 * Kein generischer POST-Proxy fuer das gesamte /v1/*.
 */
export async function POST(
  req: Request,
  ctx: { params: Promise<{ segments: string[] }> },
) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  const { segments } = await ctx.params;
  if (!segments?.length || segments[0] !== "v1") {
    return NextResponse.json(
      { detail: "Nur Pfade unter /v1/* sind erlaubt." },
      { status: 404 },
    );
  }

  const path = `/${segments.join("/")}`;
  if (!genericGatewayBffAllowsPostPath(path)) {
    return NextResponse.json(
      {
        detail:
          "POST ist hier nur fuer /v1/commerce/customer/contracts und Unterpfade erlaubt.",
      },
      { status: 403 },
    );
  }

  const body = await req.text();
  let res: Response;
  try {
    res = await fetchGatewayUpstream(path, auth.authorization, {
      method: "POST",
      body: body || "{}",
      timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
      traceSource: req.headers,
    });
  } catch (e) {
    return upstreamFetchFailedResponse(e);
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/pdf")) {
    const buf = await res.arrayBuffer();
    const headers = new Headers();
    headers.set("Content-Type", ct);
    const cd = res.headers.get("content-disposition");
    if (cd) {
      headers.set("Content-Disposition", cd);
    }
    return new NextResponse(buf, { status: res.status, headers });
  }
  const text = await res.text();
  const out = new Headers({
    "Content-Type": ct || "application/json",
  });
  out.set("Cache-Control", "no-store");
  applyGatewayReadStatusHeaders(out, text, ct || "application/json");
  return new NextResponse(text, { status: res.status, headers: out });
}

export async function PUT() {
  return gatewayCatchAllUnsupportedMethod();
}

export async function PATCH() {
  return gatewayCatchAllUnsupportedMethod();
}

export async function DELETE() {
  return gatewayCatchAllUnsupportedMethod();
}
