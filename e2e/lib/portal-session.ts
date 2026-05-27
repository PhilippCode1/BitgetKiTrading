import { SignJWT } from "jose";
import type { Page } from "@playwright/test";

import { loadGatewayJwtSecretFromRoot } from "./load-gateway-secret";

export const PORTAL_JWT_COOKIE = "bitget_portal_jwt";
export const LOCALE_COOKIE = "bitget_dashboard_locale";
export const E2E_LIVE_RIBBON_COOKIE = "e2e_fixture_live_ribbon";

/**
 * Gleiche Claims wie `loginAction` (Mock-Login) — damit Middleware-Persona=customer.
 */
export async function signE2eCustomerPortalJwt(
  secret: string,
  tenantId: string = "tenant_demo_123",
): Promise<string> {
  if (!secret.trim()) {
    throw new Error("GATEWAY_JWT_SECRET leer (E2E Portal-Session)");
  }
  const audience =
    process.env.GATEWAY_JWT_AUDIENCE?.trim() || "api-gateway";
  const issuer =
    process.env.GATEWAY_JWT_ISSUER?.trim() || "bitget-btc-ai-gateway";
  return new SignJWT({
    sub: `e2e-customer-${tenantId}`,
    role: "customer",
    portal_roles: ["customer"],
    gateway_roles: ["billing:read"],
    tenant_id: tenantId,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("2h")
    .setAudience(audience)
    .setIssuer(issuer)
    .sign(new TextEncoder().encode(secret));
}

export async function setCustomerPortalSessionCookies(
  page: Page,
  baseURL: string | undefined,
  options?: { locale?: string; tenantId?: string; liveRibbon?: boolean },
): Promise<string | null> {
  const secret = loadGatewayJwtSecretFromRoot();
  if (!secret) {
    return null;
  }
  const base = baseURL ?? "http://127.0.0.1:3000";
  const token = await signE2eCustomerPortalJwt(
    secret,
    options?.tenantId ?? "tenant_demo_123",
  );
  const secure = base.startsWith("https:");
  const cookieList: Array<{
    name: string;
    value: string;
    url: string;
    httpOnly: boolean;
    sameSite: "Lax";
    secure: boolean;
  }> = [
    {
      name: PORTAL_JWT_COOKIE,
      value: token,
      url: base,
      httpOnly: true,
      sameSite: "Lax",
      secure,
    },
    {
      name: LOCALE_COOKIE,
      value: options?.locale ?? "de",
      url: base,
      httpOnly: false,
      sameSite: "Lax",
      secure,
    },
  ];
  if (options?.liveRibbon) {
    cookieList.push({
      name: E2E_LIVE_RIBBON_COOKIE,
      value: "1",
      url: base,
      httpOnly: true,
      sameSite: "Lax",
      secure,
    });
  }
  await page.context().addCookies(cookieList);
  return token;
}
