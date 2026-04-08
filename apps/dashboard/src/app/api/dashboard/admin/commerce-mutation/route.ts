import { NextResponse } from "next/server";

import { commerceAdminMutationAllowed } from "@/lib/dashboard-bff-allowlists";
import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";

/**
 * Streng allowlistisierter Proxy fuer Commerce-Admin-Schreibpfade.
 * JWT/Key bleiben serverseitig; der Browser sendet nur Zielpfad + JSON-Body.
 */
export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "invalid_json" }, { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return NextResponse.json({ detail: "invalid_body" }, { status: 400 });
  }
  const rec = body as Record<string, unknown>;
  const method = typeof rec.method === "string" ? rec.method : "";
  const path = typeof rec.path === "string" ? rec.path : "";
  const payload = rec.payload;

  if (!commerceAdminMutationAllowed(method, path)) {
    return NextResponse.json({ detail: "path_not_allowed" }, { status: 403 });
  }

  const raw =
    payload === undefined || payload === null ? "{}" : JSON.stringify(payload);

  let res: Response;
  try {
    res = await fetchGatewayUpstream(path, auth.authorization, {
      method: method.toUpperCase(),
      body: raw,
      timeoutMs: 45_000,
    });
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
