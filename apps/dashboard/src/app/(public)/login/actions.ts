"use server";

import { cookies } from "next/headers";

import {
  buildOidcLoginStart,
  buildPortalJwtClaims,
  mintPortalJwt,
  mockLoginAvailable,
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  oidcConfigured,
  portalAuthProvider,
  portalCookieOptions,
  readPortalRole,
  readPortalTenantId,
} from "@/lib/auth/portal-auth-adapter";
import { CONSOLE_BASE, PORTAL_BASE } from "@/lib/console-paths";
import { PORTAL_JWT_COOKIE_NAME } from "@/lib/portal-persona";

type LoginActionResult =
  | { success: true; redirect: string }
  | { success: false; errorCode: string };

export async function startOidcLoginAction(
  returnTo: string,
): Promise<LoginActionResult> {
  if (portalAuthProvider() !== "oidc" || !oidcConfigured()) {
    return {
      success: false,
      errorCode: "oidc_not_configured",
    };
  }
  const start = buildOidcLoginStart(returnTo);
  if (!start) {
    return {
      success: false,
      errorCode: "oidc_start_failed",
    };
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
  return { success: true, redirect: start.authorizationUrl };
}

export async function loginAction(formData: FormData): Promise<LoginActionResult> {
  if (portalAuthProvider() === "oidc" && !mockLoginAvailable().ok) {
    return startOidcLoginAction(
      typeof formData.get("returnTo") === "string"
        ? String(formData.get("returnTo"))
        : "",
    );
  }

  const guard = mockLoginAvailable();
  if (!guard.ok) {
    return {
      success: false,
      errorCode: guard.reason ?? "mock_login_disabled",
    };
  }

  const role = readPortalRole(formData.get("role"));
  const tenantId = readPortalTenantId(formData.get("tenantId"));

  if (role === "customer" && !tenantId) {
    return {
      success: false,
      errorCode: "invalid_tenant_id",
    };
  }

  try {
    const claims = buildPortalJwtClaims(role, tenantId);
    const token = await mintPortalJwt(claims);
    const jar = await cookies();
    jar.set(PORTAL_JWT_COOKIE_NAME, token, portalCookieOptions());

    return {
      success: true,
      redirect: role === "admin" ? CONSOLE_BASE : PORTAL_BASE,
    };
  } catch (err) {
    if (err instanceof Error && err.message === "missing_gateway_jwt_secret") {
      return {
        success: false,
        errorCode: "missing_gateway_jwt_secret",
      };
    }
    console.error("[mock-login] sign_failed", err);
    return {
      success: false,
      errorCode: "sign_failed",
    };
  }
}

export async function logoutAction(): Promise<{ success: true; redirect: string }> {
  const jar = await cookies();
  jar.delete(PORTAL_JWT_COOKIE_NAME);
  return { success: true, redirect: "/login" };
}
