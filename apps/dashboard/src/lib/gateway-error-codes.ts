/**
 * Gateway- und BFF-Fehlercodes: Erkennung fuer ApiFetchError + i18n-Mapping.
 * (Quellen: services/api-gateway, lib/gateway-bff-errors.ts)
 */

import type { ApiFetchKind } from "./api-fetch-errors";
import type { FetchErrorKind } from "./user-facing-fetch-error";

const BFF_CONFIG_CODES = new Set(
  [
    "DASHBOARD_GATEWAY_AUTH_MISSING",
    "API_GATEWAY_URL_MISSING",
  ].map((c) => c.toUpperCase()),
);

const RATE_LIMIT_CODES = new Set(
  ["RATE_LIMIT_EXCEEDED", "RATE_LIMIT_BURST", "TOO_MANY_REQUESTS"].map((c) =>
    c.toUpperCase(),
  ),
);

const UPSTREAM_UNREACHABLE_CODES = new Set(
  [
    "NODE_DOWN",
    "UPSTREAM_DOWN",
    "SERVICE_UNAVAILABLE",
    "GATEWAY_TRANSPORT_FAILED",
  ].map((c) => c.toUpperCase()),
);

function norm(s: string | undefined | null): string {
  return (s ?? "").trim().toUpperCase();
}

/**
 * Liest code/layer aus Gateway-/BFF-JSON (flach oder error.code).
 */
export function extractGatewayCodeAndLayer(
  bodyText: string,
): { code?: string; layer?: string } {
  const t = bodyText.slice(0, 4000).trim();
  if (!t) return {};
  try {
    const j = JSON.parse(t) as {
      code?: unknown;
      layer?: unknown;
      error?: { code?: unknown; layer?: unknown };
    };
    let code: string | undefined;
    let layer: string | undefined;
    if (typeof j.code === "string" && j.code.trim()) code = j.code.trim();
    if (typeof j.layer === "string" && j.layer.trim()) layer = j.layer.trim();
    if (j.error && typeof j.error === "object" && !Array.isArray(j.error)) {
      const er = j.error as { code?: unknown; layer?: unknown };
      if (!code && typeof er.code === "string" && er.code.trim()) {
        code = er.code.trim();
      }
      if (!layer && typeof er.layer === "string" && er.layer.trim()) {
        layer = er.layer.trim();
      }
    }
    return { code, layer };
  } catch {
    return {};
  }
}

/**
 * Setzt feinere {@link ApiFetchKind}-Werte nach JSON-`code` / HTTP-Status
 * (z. B. 503 + DASHBOARD_GATEWAY_AUTH_MISSING -> config statt nur upstream_down).
 */
export function refineApiFetchKindForGateway(args: {
  status: number;
  baseKind: ApiFetchKind;
  code?: string;
  layer?: string;
}): ApiFetchKind {
  const { status, baseKind, code } = args;
  const c = norm(code);

  if (status === 429 || RATE_LIMIT_CODES.has(c)) {
    return "rate_limit";
  }

  if (BFF_CONFIG_CODES.has(c)) {
    return "config";
  }

  if (UPSTREAM_UNREACHABLE_CODES.has(c)) {
    if (c === "GATEWAY_TRANSPORT_FAILED") {
      return status >= 500 ? "upstream_down" : "network";
    }
    return "upstream_down";
  }

  if (
    (c === "GATEWAY_AUTH_MISSING" || c.startsWith("GATEWAY_JWT_")) &&
    (status === 401 || status === 403)
  ) {
    return "auth";
  }

  if (c === "GATEWAY_AUTH_MISSING" && (status === 502 || status === 503)) {
    return "config";
  }

  return baseKind;
}

/**
 * Direkte Zuordnung fuer {@link productMessage} / `ui.fetchError.*`
 * (schlaegt generisches {@link mapApiFetchKindToUi}).
 */
export function mapGatewayCodeToFetchErrorKind(
  code: string | undefined,
  status: number | undefined,
  _layer: string | undefined,
): FetchErrorKind | null {
  const c = norm(code);
  const st = status ?? 0;

  if (st === 429 || RATE_LIMIT_CODES.has(c)) {
    return "rate_limited";
  }

  if (BFF_CONFIG_CODES.has(c)) {
    return "configuration";
  }

  if (c === "GATEWAY_AUTH_MISSING" && (st === 502 || st === 503)) {
    return "configuration";
  }

  if (UPSTREAM_UNREACHABLE_CODES.has(c) && c !== "GATEWAY_TRANSPORT_FAILED") {
    return "bad_gateway";
  }
  if (c === "GATEWAY_TRANSPORT_FAILED") {
    return st >= 500 ? "bad_gateway" : "bff_unreachable";
  }

  return null;
}
