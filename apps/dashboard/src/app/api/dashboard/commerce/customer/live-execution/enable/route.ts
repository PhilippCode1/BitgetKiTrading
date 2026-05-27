import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  // Go-Live ist eine vom Endnutzer ausgeloeste Mutation. Wir akzeptieren
  // ausschliesslich das Portal-JWT aus dem Cookie und verweigern den
  // BFF-ENV-Fallback bewusst (kein generischer Service-Token fuer
  // tenant-spezifische Schreib-Operationen).
  const auth = requireOperatorGatewayAuth(req.headers);
  if (!auth.ok) return auth.response;
  if (auth.source !== "portal_jwt") {
    return NextResponse.json(
      {
        error: "PORTAL_SESSION_REQUIRED",
        message: "Go-Live erfordert eine Endnutzer-Session (bitget_portal_jwt).",
      },
      { status: 401 },
    );
  }

  let res: Response;
  try {
    const rawBody = await req.text();
    const body =
      rawBody.trim().length > 0 ? rawBody : JSON.stringify({ step_up_code: null });
    res = await fetchGatewayUpstream(
      "/v1/commerce/customer/live-execution/enable",
      auth.authorization,
      {
        method: "POST",
        body,
        timeoutMs: GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
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
