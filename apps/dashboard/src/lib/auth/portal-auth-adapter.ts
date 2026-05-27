/**
 * Portal-Auth-Adapter: Mock (Dev) und OIDC (Production).
 * JWT-Claims muessen mit shared_py.portal_access_contract uebereinstimmen.
 */

import { createRemoteJWKSet, jwtVerify, SignJWT, type JWTPayload } from "jose";

export type PortalAuthRole = "customer" | "admin";

export type PortalJwtClaims = {
  sub: string;
  role: string;
  gateway_roles: string[];
  portal_roles: string[];
  tenant_id: string;
};

export type OidcUserProfile = {
  sub: string;
  email?: string;
  email_verified?: boolean;
  tenant_id?: string;
  [key: string]: unknown;
};

export type OidcLoginStart = {
  authorizationUrl: string;
  state: string;
};

export const OIDC_STATE_COOKIE = "oidc_auth_state";
export const OIDC_RETURN_TO_COOKIE = "oidc_return_to";

const MOCK_LOGIN_ALLOWED_ENVS = new Set(["development", "test"]);

export function mockLoginAvailable(): { ok: boolean; reason?: string } {
  const env = (process.env.NODE_ENV ?? "development").toLowerCase();
  if (!MOCK_LOGIN_ALLOWED_ENVS.has(env)) {
    return { ok: false, reason: "mock_login_blocked_in_production" };
  }
  const explicitOptIn = (process.env.ENABLE_MOCK_LOGIN ?? "").trim().toLowerCase();
  if (env === "test" || explicitOptIn === "true" || explicitOptIn === "1") {
    return { ok: true };
  }
  if (env === "development") {
    return { ok: true };
  }
  return { ok: false, reason: "mock_login_not_enabled" };
}

export function portalAuthProvider(): "mock" | "oidc" {
  const raw = (process.env.PORTAL_AUTH_PROVIDER ?? "mock").trim().toLowerCase();
  return raw === "oidc" ? "oidc" : "mock";
}

export function loginRouteEnabled(): boolean {
  if (mockLoginAvailable().ok) return true;
  return portalAuthProvider() === "oidc" && oidcConfigured();
}

export function normalizePortalTenantId(raw: string): string {
  const s = raw.trim();
  if (!/^[a-z0-9_-]{3,64}$/i.test(s)) {
    return "";
  }
  return s;
}

export function readPortalRole(raw: FormDataEntryValue | null): PortalAuthRole {
  const s = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  return s === "admin" ? "admin" : "customer";
}

export function readPortalTenantId(raw: FormDataEntryValue | null): string {
  const s = typeof raw === "string" ? raw.trim() : "";
  return normalizePortalTenantId(s);
}

export function getGatewayJwtSigningSecret(): string | null {
  const v = (process.env.GATEWAY_JWT_SECRET ?? "").trim();
  return v.length >= 16 ? v : null;
}

export function buildPortalJwtClaims(
  role: PortalAuthRole,
  tenantId: string,
): PortalJwtClaims {
  if (role === "admin") {
    return {
      sub: "mock-admin-actor",
      role: "admin",
      gateway_roles: [
        "admin:read",
        "admin:write",
        "gateway:read",
        "operator:mutate",
        "emergency:mutate",
      ],
      portal_roles: ["super_admin"],
      tenant_id: "default",
    };
  }
  return {
    sub: `mock-customer-${tenantId}`,
    role: "customer",
    gateway_roles: ["billing:read"],
    portal_roles: ["customer"],
    tenant_id: tenantId,
  };
}

export function mapOidcProfileToPortalClaims(
  profile: OidcUserProfile,
): PortalJwtClaims | null {
  const tenantClaim = (process.env.OIDC_TENANT_CLAIM ?? "tenant_id").trim();
  const defaultTenant = (process.env.OIDC_DEFAULT_TENANT_ID ?? "").trim();
  const adminEmails = (process.env.OIDC_ADMIN_EMAILS ?? "")
    .split(",")
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
  const email =
    typeof profile.email === "string" ? profile.email.trim().toLowerCase() : "";
  if (adminEmails.length > 0 && email && adminEmails.includes(email)) {
    return {
      sub: profile.sub,
      role: "admin",
      gateway_roles: [
        "admin:read",
        "admin:write",
        "gateway:read",
        "operator:mutate",
        "emergency:mutate",
      ],
      portal_roles: ["super_admin"],
      tenant_id: "default",
    };
  }
  const rawTenant = profile[tenantClaim] ?? profile.tenant_id ?? defaultTenant;
  const tenantId =
    typeof rawTenant === "string"
      ? normalizePortalTenantId(rawTenant)
      : normalizePortalTenantId(defaultTenant);
  if (!tenantId) {
    return null;
  }
  return {
    sub: profile.sub,
    role: "customer",
    gateway_roles: ["billing:read"],
    portal_roles: ["customer"],
    tenant_id: tenantId,
  };
}

export async function mintPortalJwt(claims: PortalJwtClaims): Promise<string> {
  const secretStr = getGatewayJwtSigningSecret();
  if (!secretStr) {
    throw new Error("missing_gateway_jwt_secret");
  }
  const audience =
    (process.env.GATEWAY_JWT_AUDIENCE ?? "api-gateway").trim() || "api-gateway";
  const issuer =
    (process.env.GATEWAY_JWT_ISSUER ?? "bitget-btc-ai-gateway").trim() ||
    "bitget-btc-ai-gateway";
  return new SignJWT({ ...claims })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("2h")
    .setAudience(audience)
    .setIssuer(issuer)
    .sign(new TextEncoder().encode(secretStr));
}

function oidcIssuerBase(): string {
  return (process.env.OIDC_ISSUER ?? "").trim().replace(/\/$/, "");
}

export function getOidcAuthorizationUrl(state: string): string | null {
  const issuer = oidcIssuerBase();
  const clientId = (process.env.OIDC_CLIENT_ID ?? "").trim();
  const redirectUri = (process.env.OIDC_REDIRECT_URI ?? "").trim();
  if (!issuer || !clientId || !redirectUri) {
    return null;
  }
  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: (process.env.OIDC_SCOPES ?? "openid profile email").trim(),
    state,
  });
  const authPath =
    (process.env.OIDC_AUTHORIZE_PATH ?? "/authorize").trim() || "/authorize";
  return `${issuer}${authPath.startsWith("/") ? authPath : `/${authPath}`}?${params.toString()}`;
}

export function oidcConfigured(): boolean {
  return getOidcAuthorizationUrl("probe") !== null;
}

export function buildOidcLoginStart(_returnTo: string): OidcLoginStart | null {
  const state = crypto.randomUUID();
  const authorizationUrl = getOidcAuthorizationUrl(state);
  if (!authorizationUrl) return null;
  return { authorizationUrl, state };
}

function oidcTokenUrl(): string | null {
  const custom = (process.env.OIDC_TOKEN_URL ?? "").trim();
  if (custom) return custom;
  const issuer = oidcIssuerBase();
  if (!issuer) return null;
  const path = (process.env.OIDC_TOKEN_PATH ?? "/oauth/token").trim() || "/oauth/token";
  return `${issuer}${path.startsWith("/") ? path : `/${path}`}`;
}

function oidcJwksUrl(): string | null {
  const custom = (process.env.OIDC_JWKS_URL ?? "").trim();
  if (custom) return custom;
  const issuer = oidcIssuerBase();
  if (!issuer) return null;
  return `${issuer}/.well-known/jwks.json`;
}

export async function exchangeOidcCode(code: string): Promise<{
  idToken: string;
  accessToken?: string;
}> {
  const tokenUrl = oidcTokenUrl();
  const clientId = (process.env.OIDC_CLIENT_ID ?? "").trim();
  const clientSecret = (process.env.OIDC_CLIENT_SECRET ?? "").trim();
  const redirectUri = (process.env.OIDC_REDIRECT_URI ?? "").trim();
  if (!tokenUrl || !clientId || !redirectUri) {
    throw new Error("oidc_not_configured");
  }
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
  });
  if (clientSecret) {
    body.set("client_secret", clientSecret);
  }
  const res = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new Error(`oidc_token_exchange_failed:${res.status}`);
  }
  const json = (await res.json()) as Record<string, unknown>;
  const idToken = typeof json.id_token === "string" ? json.id_token : "";
  if (!idToken) {
    throw new Error("oidc_missing_id_token");
  }
  const accessToken =
    typeof json.access_token === "string" ? json.access_token : undefined;
  return { idToken, accessToken };
}

export async function verifyOidcIdToken(idToken: string): Promise<OidcUserProfile> {
  const issuer = oidcIssuerBase();
  const clientId = (process.env.OIDC_CLIENT_ID ?? "").trim();
  const jwksUrl = oidcJwksUrl();
  if (!issuer || !clientId || !jwksUrl) {
    throw new Error("oidc_not_configured");
  }
  const jwks = createRemoteJWKSet(new URL(jwksUrl));
  const { payload } = await jwtVerify(idToken, jwks, {
    issuer,
    audience: clientId,
  });
  return payloadToOidcProfile(payload);
}

export function payloadToOidcProfile(payload: JWTPayload): OidcUserProfile {
  const sub = typeof payload.sub === "string" ? payload.sub : "";
  if (!sub) {
    throw new Error("oidc_missing_sub");
  }
  return {
    sub,
    email: typeof payload.email === "string" ? payload.email : undefined,
    email_verified:
      payload.email_verified === true || payload.email_verified === "true",
    tenant_id:
      typeof payload.tenant_id === "string" ? payload.tenant_id : undefined,
    ...payload,
  };
}

export async function syncOidcIdentityToGateway(
  portalJwt: string,
  payload: { email_verified: boolean; mfa_totp_enabled?: boolean },
): Promise<void> {
  const base = (process.env.API_GATEWAY_URL ?? "http://api-gateway:8000").replace(
    /\/$/,
    "",
  );
  const auth = portalJwt.startsWith("Bearer ") ? portalJwt : `Bearer ${portalJwt}`;
  const res = await fetch(`${base}/v1/commerce/customer/identity/oidc-sync`, {
    method: "POST",
    headers: {
      Authorization: auth,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`oidc_identity_sync_failed:${res.status}`);
  }
}

export function portalCookieOptions(): {
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax";
  maxAge: number;
  path: string;
} {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 2,
    path: "/",
  };
}
