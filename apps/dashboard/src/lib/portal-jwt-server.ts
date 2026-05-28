import "server-only";

import { cookies } from "next/headers";

import { PORTAL_JWT_COOKIE_NAME } from "@/lib/portal-persona";

/**
 * Server-only: liest das Portal-JWT-Cookie und liefert einen normalisierten
 * Authorization-Header zurueck. Falls kein Cookie vorhanden ist, wird `null`
 * geliefert (Aufrufer muss entscheiden, wie damit umzugehen ist).
 *
 * Niemals im Client-Code verwenden — der BFF-Proxy darf den User-Token nur
 * serverseitig an das API-Gateway anhaengen.
 */
export async function readPortalAuthorizationFromCookies(): Promise<string | null> {
  let raw: string | undefined;
  try {
    const jar = await cookies();
    raw = jar.get(PORTAL_JWT_COOKIE_NAME)?.value;
  } catch {
    // outside of a request context (e.g. build): cookies() throws
    return null;
  }
  const token = (raw ?? "").trim();
  if (!token) {
    return null;
  }
  return token.startsWith("Bearer ") ? token : `Bearer ${token}`;
}

/**
 * Liest das Cookie *aus einem konkreten Request* (z. B. fuer Route Handler,
 * die `req.cookies` ueber den Standard-Cookie-Header verfuegen). Kein
 * String-Parsing — nutzt die Standard `Headers`-API.
 */
export function readPortalAuthorizationFromHeaders(
  headers: Headers | null | undefined,
): string | null {
  if (!headers) return null;
  const cookieHeader = headers.get("cookie");
  if (!cookieHeader) return null;
  // robustes Cookie-Parsing: jeder Eintrag ist `name=value; flags`,
  // Werte koennen URL-encoded sein. Wir verwenden hier eine konservative
  // Variante, da Node.js (Next 16) keine eingebaute Standard-API liefert.
  for (const pair of cookieHeader.split(";")) {
    const eq = pair.indexOf("=");
    if (eq < 0) continue;
    const name = pair.slice(0, eq).trim();
    if (name !== PORTAL_JWT_COOKIE_NAME) continue;
    let value = pair.slice(eq + 1).trim();
    if (value.startsWith('"') && value.endsWith('"') && value.length >= 2) {
      value = value.slice(1, -1);
    }
    try {
      value = decodeURIComponent(value);
    } catch {
      // already decoded
    }
    if (!value) return null;
    return value.startsWith("Bearer ") ? value : `Bearer ${value}`;
  }
  return null;
}
