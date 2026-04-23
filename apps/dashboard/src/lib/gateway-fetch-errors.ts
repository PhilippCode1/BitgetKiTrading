import { isApiFetchError, type ApiFetchError } from "./api-fetch-errors";
import {
  classifyFetchError,
  type FetchErrorKind,
} from "./user-facing-fetch-error";

export type { FetchErrorKind } from "./user-facing-fetch-error";

export type GatewayFetchErrorInfo = Readonly<{
  kind: FetchErrorKind;
  /** Für Expertenklappe / Logs — nicht als Nutzer-Lead. */
  technical: string;
}>;

function technicalLine(reason: unknown): string {
  if (isApiFetchError(reason)) {
    const e = reason as ApiFetchError;
    return JSON.stringify(
      {
        kind: e.kind,
        path: e.path,
        bffPath: e.bffPath,
        status: e.status,
        code: e.code,
        layer: e.layer,
        message: e.message,
      },
      null,
      2,
    );
  }
  return reason instanceof Error ? reason.message : String(reason);
}

/**
 * Strukturierter API-/Gateway-Fehler mit `kind` für i18n (`ui.fetchError.*` / `productMessage.fetch.*`).
 */
export function getGatewayFetchErrorInfo(reason: unknown): GatewayFetchErrorInfo {
  return {
    kind: classifyFetchError(reason),
    technical: technicalLine(reason).slice(0, 8_000),
  };
}

/**
 * @deprecated Für UI: {@link getGatewayFetchErrorInfo} + `t(…)` oder
 *   {@link userFacingBodyForFetchFailure}. Rückgabe = technische Zeile (kein Freitext-Lead).
 */
export function gatewayFetchErrorMessage(reason: unknown): string {
  return getGatewayFetchErrorInfo(reason).technical;
}
