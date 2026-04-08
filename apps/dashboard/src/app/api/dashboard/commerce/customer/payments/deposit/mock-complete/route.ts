import { NextResponse } from "next/server";

import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import { fetchGatewayWithoutBearer } from "@/lib/gateway-upstream-fetch";
import { upstreamFetchFailedResponse } from "@/lib/gateway-upstream";
import { serverEnv } from "@/lib/server-env";

export async function POST(req: Request) {
  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) return auth.response;
  const secret = serverEnv.paymentMockWebhookSecret;
  if (!secret) {
    return NextResponse.json(
      { detail: "PAYMENT_MOCK_WEBHOOK_SECRET fehlt (Dashboard-Server-ENV)" },
      { status: 503 },
    );
  }
  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  const intentId =
    typeof payload === "object" && payload !== null && "intent_id" in payload
      ? String((payload as { intent_id: unknown }).intent_id ?? "").trim()
      : "";
  if (!intentId) {
    return NextResponse.json({ detail: "intent_id required" }, { status: 400 });
  }
  let res: Response;
  try {
    res = await fetchGatewayWithoutBearer(
      "/v1/commerce/payments/webhooks/mock",
      {
        method: "POST",
        body: JSON.stringify({ intent_id: intentId }),
        extraHeaders: {
          "Content-Type": "application/json",
          "X-Payment-Mock-Secret": secret,
        },
        timeoutMs: 20_000,
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
