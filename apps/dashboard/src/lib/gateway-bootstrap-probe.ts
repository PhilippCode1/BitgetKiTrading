import { cache } from "react";

import { fetchGatewayUpstream } from "@/lib/gateway-upstream-fetch";
import { serverEnv } from "@/lib/server-env";

const HEALTH_MS = 4_000;
const READY_MS = 10_000;
const OPERATOR_HEALTH_MS = 8_000;

export type GatewayBootstrapRootCause =
  | "ok"
  | "api_gateway_url_missing"
  | "dashboard_authorization_missing"
  /** TCP/DNS/Timeout bis GET /health (Gateway-Prozess oder URL falsch). */
  | "gateway_unreachable"
  | "gateway_health_not_ok"
  | "gateway_not_ready"
  /** GET /v1/system/health: 401 Signatur/Ablauf/Rollen. */
  | "operator_jwt_unauthorized"
  /** GET /v1/system/health: 403 Policy. */
  | "operator_jwt_forbidden"
  /** Netzwerk/Timeout nach erfolgreichem /health, bei authentifizierter /v1-Anfrage. */
  | "operator_path_transport_failed"
  | "operator_health_upstream_error";

export type GatewayBootstrapProbeResult = Readonly<{
  rootCause: GatewayBootstrapRootCause;
  /** Wenn true: Server-`getJson` soll keine weiteren Upstream-Requests starten. */
  blocksV1Reads: boolean;
  /** Kurztext fuer Logs / Diagnose (keine Secrets). */
  detail: string;
  /** HTTP-Status der Gateway-/health-Antwort, sofern bekannt. */
  gatewayHealthHttpStatus: number | null;
  /** Aus Gateway-/ready JSON, sofern erfolgreich geparst. */
  gatewayReadyFlag: boolean | null;
  /** Kompakte Check-Zusammenfassung (nur nicht-prod / Diagnose). */
  gatewayReadySummary: string | null;
  operatorHealthHttpStatus: number | null;
  operatorHealthErrorSnippet: string | null;
  /** Gateway-JSON detail.code bei 401/403 (z. B. GATEWAY_JWT_EXPIRED), sofern parsebar. */
  operatorGatewayAuthCode: string | null;
  /** Gateway-JSON detail.hint, gekuerzt. */
  operatorGatewayAuthHint: string | null;
}>;

const MINT_HINT =
  "Erzeugen: python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file; Next neu starten.";
const STACK_HINT =
  "Stack: pnpm stack:local oder pnpm dev:up. Pruefen: pnpm stack:check. Diagnose: /api/dashboard/edge-status.";

function parseGatewayAuthFailureBody(text: string): {
  code?: string;
  message?: string;
  hint?: string;
} | null {
  const t = text.trim();
  if (!t.startsWith("{")) return null;
  try {
    const j = JSON.parse(t) as unknown;
    if (j == null || typeof j !== "object") return null;
    const o = j as Record<string, unknown>;
    const detail = o.detail;
    if (
      detail != null &&
      typeof detail === "object" &&
      !Array.isArray(detail)
    ) {
      const d = detail as Record<string, unknown>;
      return {
        code: typeof d.code === "string" ? d.code : undefined,
        message: typeof d.message === "string" ? d.message : undefined,
        hint: typeof d.hint === "string" ? d.hint : undefined,
      };
    }
    return null;
  } catch {
    return null;
  }
}

function summarizeReadyChecks(checks: unknown): string | null {
  if (checks == null || typeof checks !== "object") return null;
  const o = checks as Record<string, unknown>;
  const parts: string[] = [];
  for (const [k, v] of Object.entries(o)) {
    if (parts.length >= 6) break;
    if (Array.isArray(v) && v.length >= 2) {
      const ok = v[0];
      const msg = typeof v[1] === "string" ? v[1] : JSON.stringify(v[1]);
      parts.push(`${k}=${ok === true ? "ok" : "fail"}:${msg.slice(0, 80)}`);
    }
  }
  return parts.length ? parts.join("; ") : null;
}

function buildGetJsonBlockMessage(
  path: string,
  p: GatewayBootstrapProbeResult,
): string {
  const hintEnv =
    "ENV: API_GATEWAY_URL, DASHBOARD_GATEWAY_AUTHORIZATION prüfen.";
  switch (p.rootCause) {
    case "api_gateway_url_missing":
      return `GET ${path}: HTTP 503 — API_GATEWAY_URL auf dem Next-Server nicht gesetzt (oder in Production leer). ${hintEnv} ${STACK_HINT}`;
    case "dashboard_authorization_missing":
      return `GET ${path}: HTTP 503 — DASHBOARD_GATEWAY_AUTHORIZATION fehlt. ${MINT_HINT} ${STACK_HINT}`;
    case "gateway_unreachable":
      return `GET ${path}: Gateway nicht erreichbar oder Timeout (${p.detail}). ${hintEnv} ${STACK_HINT}`;
    case "operator_path_transport_failed":
      return `GET ${path}: Netzwerk/Timeout zur authentifizierten Gateway-Route (${p.detail}). JWT ist gesetzt; pruefe API_GATEWAY_URL und Gateway-Logs. ${STACK_HINT}`;
    case "gateway_health_not_ok":
      return `GET ${path}: HTTP ${p.gatewayHealthHttpStatus ?? "???"} — Gateway /health nicht OK. Logs api-gateway prüfen. ${STACK_HINT}`;
    case "gateway_not_ready":
      return `GET ${path}: HTTP 503 — API-Gateway meldet ready=false. ${p.detail || hintEnv} ${STACK_HINT}`;
    case "operator_jwt_unauthorized": {
      const code =
        p.operatorGatewayAuthCode != null
          ? ` Gateway-Code: ${p.operatorGatewayAuthCode}.`
          : "";
      const h =
        p.operatorGatewayAuthHint != null
          ? ` ${p.operatorGatewayAuthHint.slice(0, 220)}`
          : "";
      return `GET ${path}: HTTP 401 — Gateway lehnt JWT ab.${code}${h} Typisch: abgelaufen (GATEWAY_JWT_EXPIRED), falsches Secret (GATEWAY_JWT_INVALID) oder fehlender Header — nicht INTERNAL_API_KEY.${MINT_HINT} ${STACK_HINT}`;
    }
    case "operator_jwt_forbidden":
      return `GET ${path}: HTTP 403 — JWT ok, aber Rollen reichen nicht (GATEWAY_INSUFFICIENT_ROLES / Policy). gateway:read bzw. admin:read prüfen. ${MINT_HINT} ${STACK_HINT}`;
    case "operator_health_upstream_error":
      return `GET ${path}: HTTP ${p.operatorHealthHttpStatus ?? "502"} — GET /v1/system/health fehlgeschlagen. ${p.operatorHealthErrorSnippet ?? p.detail} ${STACK_HINT}`;
    default:
      return `GET ${path}: HTTP 503 — Gateway-Bootstrap unbekannter Zustand. ${STACK_HINT}`;
  }
}

export function blockedV1MessageForPath(
  path: string,
  p: GatewayBootstrapProbeResult,
): string {
  return buildGetJsonBlockMessage(path, p);
}

/**
 * Einmal pro React-Request (Server Components): aktive Gateway-/JWT-/ready-Diagnose.
 */
const _noOperatorAuthFields = {
  operatorGatewayAuthCode: null as string | null,
  operatorGatewayAuthHint: null as string | null,
};

export async function runGatewayBootstrapProbe(): Promise<GatewayBootstrapProbeResult> {
  const baseRaw = serverEnv.apiGatewayUrl.trim().replace(/\/$/, "");
  const hasAuth = Boolean(serverEnv.gatewayAuthorizationHeader);
  const authHeader = serverEnv.gatewayAuthorizationHeader;

  if (!baseRaw) {
    return {
      rootCause: "api_gateway_url_missing",
      blocksV1Reads: true,
      detail: "API_GATEWAY_URL leer (Production) bzw. nicht gesetzt.",
      gatewayHealthHttpStatus: null,
      gatewayReadyFlag: null,
      gatewayReadySummary: null,
      operatorHealthHttpStatus: null,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  }

  let gatewayHealthHttpStatus: number | null = null;
  try {
    const r = await fetch(`${baseRaw}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(HEALTH_MS),
    });
    gatewayHealthHttpStatus = r.status;
    if (!r.ok) {
      return {
        rootCause: "gateway_health_not_ok",
        blocksV1Reads: true,
        detail: `HTTP ${r.status} von GET /health`,
        gatewayHealthHttpStatus,
        gatewayReadyFlag: null,
        gatewayReadySummary: null,
        operatorHealthHttpStatus: null,
        operatorHealthErrorSnippet: null,
        ..._noOperatorAuthFields,
      };
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return {
      rootCause: "gateway_unreachable",
      blocksV1Reads: true,
      detail: msg,
      gatewayHealthHttpStatus: null,
      gatewayReadyFlag: null,
      gatewayReadySummary: null,
      operatorHealthHttpStatus: null,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  }

  if (!hasAuth || !authHeader) {
    return {
      rootCause: "dashboard_authorization_missing",
      blocksV1Reads: true,
      detail: "DASHBOARD_GATEWAY_AUTHORIZATION nicht gesetzt.",
      gatewayHealthHttpStatus,
      gatewayReadyFlag: null,
      gatewayReadySummary: null,
      operatorHealthHttpStatus: null,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  }

  let gatewayReadyFlag: boolean | null = null;
  let gatewayReadySummary: string | null = null;
  try {
    const rr = await fetch(`${baseRaw}/ready`, {
      cache: "no-store",
      signal: AbortSignal.timeout(READY_MS),
    });
    if (rr.ok) {
      try {
        const j = (await rr.json()) as { ready?: boolean; checks?: unknown };
        gatewayReadyFlag = typeof j.ready === "boolean" ? j.ready : null;
        gatewayReadySummary = summarizeReadyChecks(j.checks);
      } catch {
        gatewayReadyFlag = null;
      }
    }
  } catch {
    /* ready optional: health ok reicht fuer JWT-Probe */
  }

  if (gatewayReadyFlag === false) {
    const detail = gatewayReadySummary
      ? `Checks: ${gatewayReadySummary.slice(0, 400)}`
      : "Peer- oder DB/Redis-Checks schlagen fehl (siehe Gateway GET /ready).";
    return {
      rootCause: "gateway_not_ready",
      blocksV1Reads: true,
      detail,
      gatewayHealthHttpStatus,
      gatewayReadyFlag: false,
      gatewayReadySummary,
      operatorHealthHttpStatus: null,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  }

  try {
    const oh = await fetchGatewayUpstream("/v1/system/health", authHeader, {
      timeoutMs: OPERATOR_HEALTH_MS,
    });
    const opSt = oh.status;
    if (opSt === 401) {
      const raw401 = await oh.text();
      const txt = raw401.replace(/\s+/g, " ").trim().slice(0, 360);
      const parsed = parseGatewayAuthFailureBody(raw401);
      return {
        rootCause: "operator_jwt_unauthorized",
        blocksV1Reads: true,
        detail: txt || "HTTP 401",
        gatewayHealthHttpStatus,
        gatewayReadyFlag,
        gatewayReadySummary,
        operatorHealthHttpStatus: opSt,
        operatorHealthErrorSnippet: txt || null,
        operatorGatewayAuthCode: parsed?.code ?? null,
        operatorGatewayAuthHint: parsed?.hint
          ? parsed.hint.slice(0, 400)
          : null,
      };
    }
    if (opSt === 403) {
      const raw403 = await oh.text();
      const txt = raw403.replace(/\s+/g, " ").trim().slice(0, 360);
      const parsed = parseGatewayAuthFailureBody(raw403);
      return {
        rootCause: "operator_jwt_forbidden",
        blocksV1Reads: true,
        detail: txt || "HTTP 403",
        gatewayHealthHttpStatus,
        gatewayReadyFlag,
        gatewayReadySummary,
        operatorHealthHttpStatus: opSt,
        operatorHealthErrorSnippet: txt || null,
        operatorGatewayAuthCode: parsed?.code ?? null,
        operatorGatewayAuthHint: parsed?.hint
          ? parsed.hint.slice(0, 400)
          : null,
      };
    }
    if (!oh.ok) {
      const txt = (await oh.text()).replace(/\s+/g, " ").trim().slice(0, 360);
      return {
        rootCause: "operator_health_upstream_error",
        blocksV1Reads: true,
        detail: txt || `HTTP ${opSt}`,
        gatewayHealthHttpStatus,
        gatewayReadyFlag,
        gatewayReadySummary,
        operatorHealthHttpStatus: opSt,
        operatorHealthErrorSnippet: txt || null,
        ..._noOperatorAuthFields,
      };
    }
    return {
      rootCause: "ok",
      blocksV1Reads: false,
      detail: "ok",
      gatewayHealthHttpStatus,
      gatewayReadyFlag,
      gatewayReadySummary,
      operatorHealthHttpStatus: opSt,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return {
      rootCause: "operator_path_transport_failed",
      blocksV1Reads: true,
      detail: msg,
      gatewayHealthHttpStatus,
      gatewayReadyFlag,
      gatewayReadySummary,
      operatorHealthHttpStatus: null,
      operatorHealthErrorSnippet: null,
      ..._noOperatorAuthFields,
    };
  }
}

export const getGatewayBootstrapProbeForRequest = cache(
  runGatewayBootstrapProbe,
);
