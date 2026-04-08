import { isApiFetchError, type ApiFetchError } from "@/lib/api-fetch-errors";
import {
  classifyFetchError,
  type FetchErrorKind,
  type TranslateFn,
} from "@/lib/user-facing-fetch-error";

import type { ProductMessage, ProductMessageSeverity } from "./schema";

function severityForFetchKind(kind: FetchErrorKind): ProductMessageSeverity {
  switch (kind) {
    case "unauthorized":
    case "forbidden":
    case "configuration":
      return "blocking";
    case "unreachable":
    case "bff_unreachable":
    case "bad_gateway":
    case "timeout":
      return "critical";
    case "server_error":
    case "parse":
    case "validation":
    case "not_found":
      return "warning";
    default:
      return "warning";
  }
}

function baseKeys(kind: FetchErrorKind): string {
  return `productMessage.fetch.${kind}`;
}

function technicalFromError(raw: string, err: unknown): string {
  if (isApiFetchError(err)) {
    const e = err as ApiFetchError;
    return JSON.stringify(
      {
        kind: e.kind,
        path: e.path,
        bffPath: e.bffPath,
        status: e.status,
        code: e.code,
        layer: e.layer,
        retryable: e.retryable,
        message: e.message,
      },
      null,
      2,
    );
  }
  return raw.slice(0, 4000);
}

/**
 * Roh-Fehlerstring oder ApiFetchError → standardisierte Produktmeldung.
 */
export function buildProductMessageFromFetchError(
  err: unknown,
  t: TranslateFn,
): ProductMessage {
  const raw = err instanceof Error ? err.message : String(err);
  const kind = classifyFetchError(err);
  const prefix = baseKeys(kind);
  const severity = severityForFetchKind(kind);

  const code =
    isApiFetchError(err) && err.code
      ? String(err.code)
      : undefined;
  const status =
    isApiFetchError(err) && err.status != null
      ? String(err.status)
      : undefined;
  const dedupeKey = `fetch:${kind}:${code ?? status ?? "na"}`;

  return {
    id: `fetch:${dedupeKey}`,
    dedupeKey,
    severity,
    areaLabel: t("productMessage.area.thisView"),
    headline: t(`${prefix}.headline`),
    summary: t(`${prefix}.summary`),
    impact: t(`${prefix}.impact`),
    urgency: t(`${prefix}.urgency`),
    appDoing: t(`${prefix}.appDoing`),
    userAction: t(`${prefix}.userAction`),
    technicalDetail: technicalFromError(raw, err),
  };
}

/** Nur für Stellen, die noch klassifizieren müssen (Legacy-String). */
export function buildProductMessageFromFetchErrorMessage(
  raw: string,
  t: TranslateFn,
): ProductMessage {
  return buildProductMessageFromFetchError(new Error(raw), t);
}
