import { type JWTPayload, decodeJwt, jwtVerify } from "jose";

const HS256 = "HS256" as const;

/**
 * BFF -> Gateway-Identitaet. Rollen/Claims wie api-gateway (gateway_roles, portal_roles).
 * Kein NEXT_PUBLIC_*: nur serverseitige ENV, kryptographisch (HS256) gegen GATEWAY_JWT_SECRET
 * geprueft, sofern gesetzt.
 */
export type OperatorSession = Readonly<{
  role: "admin" | "none";
  sub: string | null;
}>;

/** Endkunden- vs. Operator-UI: aus portal_roles / gateway_roles (Kunden-JWT im Cookie `bitget_portal_jwt`). */
export type DashboardPersona = "customer" | "operator" | "unknown";

function stripBearer(authorization: string | undefined | null): string {
  return (authorization ?? "")
    .trim()
    .replace(/^Bearer\s+/i, "")
    .trim();
}

function asStringList(claim: unknown, scopeFallback: unknown): string[] {
  if (Array.isArray(claim)) {
    return claim.map((x) => String(x).trim()).filter((s) => s.length > 0);
  }
  if (typeof claim === "string" && claim.trim()) {
    return claim.split(/\s+/);
  }
  if (typeof scopeFallback === "string" && scopeFallback.trim()) {
    return scopeFallback.split(/\s+/);
  }
  return [];
}

/**
 * Wie Gateway: Kunden-Portal-Token (customer in portal) darf die Admin-UI nicht sehen.
 */
function mapPayloadToSession(payload: JWTPayload): OperatorSession {
  const sub = typeof payload.sub === "string" ? payload.sub : null;
  const gatewayRoles = asStringList(payload["gateway_roles"], payload["scope"]);
  const portal = new Set(
    asStringList(payload["portal_roles"], null).concat(
      typeof payload["platform_role"] === "string" &&
        payload["platform_role"].trim()
        ? [payload["platform_role"].trim()]
        : [],
    ),
  );
  const isSuper = portal.has("super_admin");
  const isCustomer = portal.has("customer");
  if (isCustomer && !isSuper) {
    return { role: "none", sub };
  }
  const roleClaim =
    typeof payload["role"] === "string"
      ? payload["role"].trim().toLowerCase()
      : "";
  const hasAdmin =
    gatewayRoles.includes("admin:read") || gatewayRoles.includes("admin:write");
  if (hasAdmin && roleClaim === "admin") {
    return { role: "admin", sub };
  }
  return { role: "none", sub };
}

function mapPayloadToDashboardPersona(payload: JWTPayload): DashboardPersona {
  const portal = new Set(
    asStringList(payload["portal_roles"], null).concat(
      typeof payload["platform_role"] === "string" &&
        payload["platform_role"].trim()
        ? [payload["platform_role"].trim()]
        : [],
    ),
  );
  if (portal.has("super_admin")) {
    return "operator";
  }
  const mainRole =
    typeof payload["role"] === "string" ? payload["role"].trim().toLowerCase() : "";
  if (mainRole === "customer") {
    return "customer";
  }
  if (portal.has("customer")) {
    return "customer";
  }
  const gatewayRoles = asStringList(payload["gateway_roles"], payload["scope"]);
  if (
    gatewayRoles.includes("admin:read") ||
    gatewayRoles.includes("admin:write")
  ) {
    return "operator";
  }
  if (gatewayRoles.length > 0) {
    return "operator";
  }
  return "unknown";
}

async function loadVerifiedPayload(
  bearerOrRaw: string | null | undefined,
  gatewayJwtSecret: string | null | undefined,
): Promise<JWTPayload | null> {
  const token = stripBearer(bearerOrRaw);
  if (!token) {
    return null;
  }
  const secret = (gatewayJwtSecret ?? "").trim() || null;
  if (secret) {
    try {
      const { payload } = await jwtVerify(
        token,
        new TextEncoder().encode(secret),
        { algorithms: [HS256] },
      );
      return payload;
    } catch {
      return null;
    }
  }
  try {
    const payload = decodeJwt(token);
    const now = Math.floor(Date.now() / 1000);
    if (typeof payload.exp === "number" && payload.exp < now) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

/**
 * DASHBOARD_GATEWAY_AUTHORIZATION (serverseitig) auswerten.
 * Ohne Secret: decodeJwt + exp (nur fuer lokale Dev, wenn Secret in .env fehlt).
 */
export async function resolveOperatorSessionFromToken(
  bearerOrRaw: string | null | undefined,
  gatewayJwtSecret: string | null | undefined,
): Promise<OperatorSession | null> {
  const payload = await loadVerifiedPayload(bearerOrRaw, gatewayJwtSecret);
  if (!payload) {
    return null;
  }
  return mapPayloadToSession(payload);
}

/**
 * Endnutzer- vs. Konsole: gleiche HS256-Pruefung wie {@link resolveOperatorSessionFromToken}.
 * Typischerweise Cookie `bitget_portal_jwt` (Mandanten-JWT), nicht BFF-ENV.
 */
export async function resolveDashboardPersonaFromToken(
  bearerOrRaw: string | null | undefined,
  gatewayJwtSecret: string | null | undefined,
): Promise<DashboardPersona> {
  const payload = await loadVerifiedPayload(bearerOrRaw, gatewayJwtSecret);
  if (!payload) {
    return "unknown";
  }
  return mapPayloadToDashboardPersona(payload);
}

/**
 * Fuer next/middleware: ENV zur Laufzeit lesen, nicht importzeitlich cachen.
 * Kein oeffentlicher Build-Key.
 */
export async function hasAdminSessionFromDashboardEnv(): Promise<boolean> {
  const auth = (process.env.DASHBOARD_GATEWAY_AUTHORIZATION ?? "").trim();
  const secret = (process.env.GATEWAY_JWT_SECRET ?? "").trim() || null;
  const s = await resolveOperatorSessionFromToken(auth, secret);
  return s?.role === "admin";
}
