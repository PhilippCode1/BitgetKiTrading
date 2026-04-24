import {
  extractGatewayCodeAndLayer,
  refineApiFetchKindForGateway,
} from "./gateway-error-codes";

/**
 * Typisierte Fetch-Fehler fuer Dashboard → Gateway / BFF (keine stillen Fallbacks).
 * UI kann `kind` gezielt mappen; `message` bleibt fuer Logs/Legacy `Error`-Ketten nutzbar.
 */

export type ApiFetchKind =
  | "config"
  | "network"
  | "timeout"
  | "auth"
  | "forbidden"
  | "not_found"
  | "validation"
  | "upstream_down"
  | "upstream_error"
  | "empty"
  | "schema"
  | "parse"
  | "rate_limit";

export type ApiFetchErrorInit = Readonly<{
  kind: ApiFetchKind;
  message: string;
  path: string;
  bffPath?: string;
  status?: number;
  code?: string;
  layer?: string;
  retryable?: boolean;
  cause?: unknown;
}>;

/**
 * Standardisierter Fetch-Fehler vom Gateway/BFF. Nutzertexte in der UI nicht aus
 * `message` ableiten — dafür `buildProductMessageFromFetchError` bzw. `userFacingBodyForFetchFailure`
 * (Keys `productMessage.fetch.*` / `ui.fetchError.*`).
 */
export class ApiFetchError extends Error {
  readonly kind: ApiFetchKind;
  readonly path: string;
  readonly bffPath?: string;
  readonly status?: number;
  readonly code?: string;
  readonly layer?: string;
  readonly retryable: boolean;

  constructor(init: ApiFetchErrorInit) {
    super(init.message);
    this.name = "ApiFetchError";
    this.kind = init.kind;
    this.path = init.path;
    this.bffPath = init.bffPath;
    this.status = init.status;
    this.code = init.code;
    this.layer = init.layer;
    this.retryable = init.retryable ?? false;
    if (init.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = init.cause;
    }
  }
}

export function isApiFetchError(e: unknown): e is ApiFetchError {
  return e instanceof ApiFetchError;
}

/** Rohtext aus Gateway/BFF JSON detail/message/code (max. Länge). */
export function extractErrorDetailFromBody(text: string): string {
  const slice = text.slice(0, 800).trim();
  if (!slice) return "";
  try {
    const j = JSON.parse(text) as {
      detail?: unknown;
      message?: unknown;
      code?: unknown;
      layer?: unknown;
      error?: {
        code?: unknown;
        message?: unknown;
        layer?: unknown;
      };
    };

    if (j.error && typeof j.error === "object" && !Array.isArray(j.error)) {
      const er = j.error as Record<string, unknown>;
      const msg =
        typeof er.message === "string" && er.message.trim()
          ? er.message.trim().slice(0, 720)
          : "";
      const code = typeof er.code === "string" ? er.code.trim() : "";
      const layer = typeof er.layer === "string" ? er.layer.trim() : "";
      let body = msg || "Request failed";
      if (code && !body.includes(code)) {
        const tag = layer ? ` [${layer}:${code}]` : ` [code:${code}]`;
        body = (body + tag).slice(0, 800);
      }
      return body.slice(0, 800);
    }

    let body = "";
    if (typeof j.detail === "string") body = j.detail.slice(0, 760);
    else if (
      j.detail != null &&
      typeof j.detail === "object" &&
      !Array.isArray(j.detail)
    ) {
      const d = j.detail as Record<string, unknown>;
      if (typeof d.message === "string" && d.message.trim())
        body = d.message.trim().slice(0, 760);
      else if (typeof d.msg === "string" && d.msg.trim())
        body = d.msg.trim().slice(0, 760);
      else body = JSON.stringify(j.detail).slice(0, 760);
      if (
        typeof d.code === "string" &&
        d.code.trim() &&
        !body.includes(d.code)
      ) {
        body = `${body} [code:${d.code}]`.slice(0, 800);
      }
    } else if (j.detail != null) body = JSON.stringify(j.detail).slice(0, 760);
    else if (typeof j.message === "string") body = j.message.slice(0, 760);
    else body = slice;
    if (typeof j.code === "string" && j.code.trim()) {
      const tag =
        j.layer === "dashboard-bff"
          ? ` [dashboard-bff:${j.code}]`
          : ` [code:${j.code}]`;
      body = (body + tag).slice(0, 800);
    }
    return body;
  } catch {
    /* plain text or HTML */
  }
  return slice;
}

function kindForStatus(status: number): ApiFetchKind {
  if (status === 401) return "auth";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 408 || status === 504) return "timeout";
  if (status === 422) return "validation";
  if (status === 429) return "rate_limit";
  if (status === 502 || status === 503) return "upstream_down";
  if (status >= 500) return "upstream_error";
  return "upstream_error";
}

function isSchemaHint(detail: string, status: number): boolean {
  if (status !== 503 && status !== 500) return false;
  const d = detail.toLowerCase();
  return (
    d.includes("migration") ||
    d.includes("schema") ||
    d.includes("undefinedtable") ||
    d.includes("relation") ||
    d.includes("does not exist")
  );
}

export function apiFetchErrorFromHttp(args: {
  path: string;
  bffPath?: string;
  status: number;
  bodyText: string;
}): ApiFetchError {
  const detail = extractErrorDetailFromBody(args.bodyText);
  const tail = detail ? ` — ${detail}` : "";
  const { code, layer } = extractGatewayCodeAndLayer(args.bodyText);
  const baseKind = isSchemaHint(detail, args.status)
    ? "schema"
    : kindForStatus(args.status);
  const kind = refineApiFetchKindForGateway({
    status: args.status,
    baseKind,
    code,
    layer,
  });
  return new ApiFetchError({
    kind,
    path: args.path,
    bffPath: args.bffPath,
    status: args.status,
    code,
    layer,
    message: `GET ${args.path}: HTTP ${args.status}${tail}`,
    retryable: false,
  });
}

export function apiFetchErrorNetwork(
  path: string,
  cause: unknown,
  bffPath?: string,
): ApiFetchError {
  const net = cause instanceof Error ? cause.message : String(cause);
  return new ApiFetchError({
    kind: "network",
    path,
    bffPath,
    message: bffPath
      ? `${bffPath}: Dashboard-BFF nicht erreichbar (${net}).`
      : `GET ${path}: Gateway nicht erreichbar oder Timeout (${net}). ENV: API_GATEWAY_URL, DASHBOARD_GATEWAY_AUTHORIZATION prüfen; Stack starten.`,
    retryable: false,
    cause,
  });
}

export function apiFetchErrorTimeout(
  path: string,
  bffPath?: string,
): ApiFetchError {
  return new ApiFetchError({
    kind: "timeout",
    path,
    bffPath,
    message: bffPath
      ? `${bffPath}: Zeitüberschreitung beim BFF-Aufruf.`
      : `GET ${path}: Zeitüberschreitung beim Gateway-Aufruf.`,
    retryable: false,
  });
}

export function apiFetchErrorParse(
  path: string,
  bffPath?: string,
): ApiFetchError {
  return new ApiFetchError({
    kind: "parse",
    path,
    bffPath,
    message: bffPath
      ? `${bffPath}: Ungueltige JSON-Antwort vom BFF.`
      : `GET ${path}: Antwort ist kein gueltiges JSON.`,
    retryable: false,
  });
}

export function apiFetchErrorConfig(
  path: string,
  message: string,
): ApiFetchError {
  return new ApiFetchError({
    kind: "config",
    path,
    message,
    retryable: false,
  });
}
