/**
 * Roh-Fehlermeldungen von fetch/getJson in produktive Kurztexte mappen.
 * Technische Details nur bei Diagnosemodus (?diagnostic=1) anzeigen.
 */

import { isApiFetchError, type ApiFetchKind } from "@/lib/api-fetch-errors";
import { mapGatewayCodeToFetchErrorKind } from "@/lib/gateway-error-codes";

export type FetchErrorKind =
  | "unreachable"
  | "timeout"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "bad_gateway"
  | "server_error"
  | "validation"
  | "parse"
  | "bff_unreachable"
  | "configuration"
  | "rate_limited"
  | "unknown";

const FETCH_ERROR_KINDS: ReadonlySet<string> = new Set<FetchErrorKind>([
  "unreachable",
  "timeout",
  "unauthorized",
  "forbidden",
  "not_found",
  "bad_gateway",
  "server_error",
  "validation",
  "parse",
  "bff_unreachable",
  "configuration",
  "rate_limited",
  "unknown",
]);

export function isValidFetchErrorKind(s: string): s is FetchErrorKind {
  return FETCH_ERROR_KINDS.has(s);
}

/** Mappt typisierte ApiFetchError.kind auf UI-FetchErrorKind (Legacy-Strings bleiben parallel). */
export function mapApiFetchKindToUi(kind: ApiFetchKind): FetchErrorKind {
  switch (kind) {
    case "network":
      return "unreachable";
    case "timeout":
      return "timeout";
    case "auth":
      return "unauthorized";
    case "forbidden":
      return "forbidden";
    case "not_found":
      return "not_found";
    case "validation":
      return "validation";
    case "upstream_down":
      return "bad_gateway";
    case "upstream_error":
      return "server_error";
    case "parse":
      return "parse";
    case "config":
      return "configuration";
    case "empty":
      return "unknown";
    case "schema":
      return "bad_gateway";
    case "rate_limit":
      return "rate_limited";
    default:
      return "unknown";
  }
}

export function classifyFetchError(err: unknown): FetchErrorKind {
  if (isApiFetchError(err)) {
    const fromCode = mapGatewayCodeToFetchErrorKind(
      err.code,
      err.status,
      err.layer,
    );
    if (fromCode) return fromCode;
    return mapApiFetchKindToUi(err.kind);
  }
  const raw = err instanceof Error ? err.message : String(err);
  return classifyFetchErrorMessage(raw);
}

export function classifyFetchErrorMessage(raw: string): FetchErrorKind {
  const s = raw.toLowerCase();
  if (
    /api_gateway_url|dashboard_gateway_authorization|gateway_authorization|env:\s*api_gateway|\.env\.local|next_public_admin|next_public_api|gateway_jwt_secret|health_url_[a-z0-9_]+/i.test(
      raw,
    ) ||
    (/bearer\s+jwt|gateway:read/i.test(raw) &&
      /mint|authorization header|dashboard-server/i.test(s))
  ) {
    return "configuration";
  }
  if (/\bhttp\s*401\b|\b401\b/.test(raw)) return "unauthorized";
  if (/\bhttp\s*403\b|\b403\b/.test(raw)) return "forbidden";
  if (/\bhttp\s*404\b|\b404\b/.test(raw)) return "not_found";
  if (/\bhttp\s*422\b|\b422\b/.test(raw)) return "validation";
  if (/\bhttp\s*502\b|\b502\b|bad gateway/i.test(raw)) return "bad_gateway";
  if (/\bhttp\s*503\b|\b503\b/.test(raw)) return "bad_gateway";
  if (/\bhttp\s*504\b|\b504\b/.test(raw)) return "timeout";
  if (/\bhttp\s*5\d{2}\b/.test(raw)) return "server_error";
  if (
    /nicht erreichbar|econnrefused|enotfound|network error|failed to fetch|fetch failed/i.test(
      s,
    )
  ) {
    return "unreachable";
  }
  if (/timeout|timed out|abort/i.test(s)) return "timeout";
  if (/json|ungueltig|ungültig|parse|kein gueltiges/i.test(s)) return "parse";
  if (/dashboard-bff|\/api\/dashboard\/gateway/i.test(s))
    return "bff_unreachable";
  return "unknown";
}

export type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

export function translateFetchError(
  raw: string | unknown,
  t: TranslateFn,
): {
  title: string;
  body: string;
  refreshHint: string;
} {
  const kind =
    typeof raw === "string"
      ? classifyFetchErrorMessage(raw)
      : classifyFetchError(raw);
  const base = `ui.fetchError.${kind}`;
  return {
    title: t(`${base}.title`),
    body: t(`${base}.body`),
    refreshHint: t("ui.refreshHint"),
  };
}

/** Kurzer, lokalisierter Nutzertext — für Server-Seiten ohne Roh-Gateway-JSON. */
export function userFacingBodyForFetchFailure(
  reason: unknown,
  t: TranslateFn,
): string {
  const k = classifyFetchError(reason);
  return t(`ui.fetchError.${k}.body`);
}
