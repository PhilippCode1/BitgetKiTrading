import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  buildOidcLoginStart,
  exchangeOidcCode,
  mapOidcProfileToPortalClaims,
  mintPortalJwt,
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  oidcConfigured,
  portalAuthProvider,
  portalCookieOptions,
  syncOidcIdentityToGateway,
  verifyOidcIdToken,
} from "@/lib/auth/portal-auth-adapter";
import { CONSOLE_BASE, PORTAL_BASE } from "@/lib/console-paths";
import { PORTAL_JWT_COOKIE_NAME } from "@/lib/portal-persona";
import { sanitizeReturnTo } from "@/lib/return-to-safety";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  if (portalAuthProvider() !== "oidc" || !oidcConfigured()) {
    return NextResponse.json({ error: "oidc_not_enabled" }, { status: 404 });
  }

  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const oauthError = url.searchParams.get("error");

  if (oauthError) {
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(oauthError)}`, url.origin),
    );
  }
  if (!code || !state) {
    return NextResponse.json({ error: "missing_code_or_state" }, { status: 400 });
  }

  const jar = await cookies();
  const expectedState = jar.get(OIDC_STATE_COOKIE)?.value ?? "";
  if (!expectedState || expectedState !== state) {
    return NextResponse.json({ error: "invalid_oidc_state" }, { status: 400 });
  }

  const returnToRaw = jar.get(OIDC_RETURN_TO_COOKIE)?.value ?? "";
  const returnTo = sanitizeReturnTo(returnToRaw, "");

  try {
    const tokens = await exchangeOidcCode(code);
    const profile = await verifyOidcIdToken(tokens.idToken);
    const claims = mapOidcProfileToPortalClaims(profile);
    if (!claims) {
      return NextResponse.json({ error: "oidc_tenant_missing" }, { status: 400 });
    }

    const portalJwt = await mintPortalJwt(claims);
    await syncOidcIdentityToGateway(portalJwt, {
      email_verified: profile.email_verified === true,
      mfa_totp_enabled: false,
    });

    jar.set(PORTAL_JWT_COOKIE_NAME, portalJwt, portalCookieOptions());
    jar.delete(OIDC_STATE_COOKIE);
    jar.delete(OIDC_RETURN_TO_COOKIE);

    const redirectPath =
      returnTo ||
      (claims.portal_roles.includes("super_admin") ? CONSOLE_BASE : PORTAL_BASE);
    return NextResponse.redirect(new URL(redirectPath, url.origin));
  } catch (err) {
    console.error("[oidc-callback] failed", err);
    return NextResponse.redirect(
      new URL("/login?error=oidc_callback_failed", url.origin),
    );
  }
}

export async function POST(req: Request) {
  if (portalAuthProvider() !== "oidc" || !oidcConfigured()) {
    return NextResponse.json({ error: "oidc_not_enabled" }, { status: 404 });
  }
  let returnTo = "";
  try {
    const body = (await req.json()) as { returnTo?: string };
    returnTo = sanitizeReturnTo(body.returnTo ?? "", "");
  } catch {
    returnTo = "";
  }
  const start = buildOidcLoginStart(returnTo);
  if (!start) {
    return NextResponse.json({ error: "oidc_not_configured" }, { status: 500 });
  }
  const jar = await cookies();
  jar.set(OIDC_STATE_COOKIE, start.state, {
    ...portalCookieOptions(),
    maxAge: 600,
  });
  if (returnTo) {
    jar.set(OIDC_RETURN_TO_COOKIE, returnTo, {
      ...portalCookieOptions(),
      maxAge: 600,
    });
  }
  return NextResponse.json({ authorizationUrl: start.authorizationUrl });
}
