import { randomUUID } from "crypto";

import { NextResponse } from "next/server";

import { runGatewayBootstrapProbe } from "@/lib/gateway-bootstrap-probe";
import type { GatewayBootstrapRootCause } from "@/lib/gateway-bootstrap-probe";
import { publicEnv } from "@/lib/env";
import { gatewayBaseUrl } from "@/lib/gateway-upstream";
import { serverEnv } from "@/lib/server-env";

export const dynamic = "force-dynamic";

/** Stabile Kurzform fuer Monitoring/Clients (unabhaengig von internen rootCause-Namen). */
export type EdgeDiagnostic =
  | "ok"
  | "jwt_missing"
  | "jwt_invalid_401"
  | "jwt_forbidden_403"
  | "gateway_url_missing"
  | "gateway_unreachable"
  | "gateway_health_failed"
  | "gateway_not_ready"
  | "operator_upstream_http_error"
  | "operator_path_transport_failed";

function edgeDiagnosticFromRootCause(
  rc: GatewayBootstrapRootCause,
): EdgeDiagnostic {
  switch (rc) {
    case "ok":
      return "ok";
    case "dashboard_authorization_missing":
      return "jwt_missing";
    case "operator_jwt_unauthorized":
      return "jwt_invalid_401";
    case "operator_jwt_forbidden":
      return "jwt_forbidden_403";
    case "api_gateway_url_missing":
      return "gateway_url_missing";
    case "gateway_unreachable":
      return "gateway_unreachable";
    case "gateway_health_not_ok":
      return "gateway_health_failed";
    case "gateway_not_ready":
      return "gateway_not_ready";
    case "operator_health_upstream_error":
      return "operator_upstream_http_error";
    case "operator_path_transport_failed":
      return "operator_path_transport_failed";
  }
}

function gatewayHealthLabel(
  probe: Awaited<ReturnType<typeof runGatewayBootstrapProbe>>,
): "ok" | "error" | "down" {
  const st = probe.gatewayHealthHttpStatus;
  if (st == null) return "down";
  if (st >= 200 && st < 300) return "ok";
  return "error";
}

function edgeHint(
  probe: Awaited<ReturnType<typeof runGatewayBootstrapProbe>>,
): string | null {
  switch (probe.rootCause) {
    case "ok":
      return null;
    case "api_gateway_url_missing":
      return "API_GATEWAY_URL auf dem Next-Server setzen (siehe docs/LOCAL_START_MINIMUM.md).";
    case "dashboard_authorization_missing":
      return "DASHBOARD_GATEWAY_AUTHORIZATION setzen (Mint-Skript), Next neu starten.";
    case "gateway_unreachable":
      return "Backend starten: pnpm stack:local / pnpm dev:up. Prüfen: pnpm stack:check. API_GATEWAY_URL muss vom Next-Host aus erreichbar sein.";
    case "gateway_health_not_ok":
      return "Gateway antwortet, aber /health nicht OK — Logs api-gateway prüfen.";
    case "gateway_not_ready":
      return "GET /ready am Gateway zeigt ready=false — HEALTH_URL_* im Container prüfen (Docker-Dienstnamen).";
    case "operator_jwt_unauthorized":
      return (
        "HTTP 401 auf /v1/system/health: Gateway-JSON enthält code (z. B. GATEWAY_JWT_EXPIRED, GATEWAY_JWT_INVALID, " +
        "GATEWAY_AUTH_MISSING). Das ist nicht INTERNAL_API_KEY — BFF nutzt nur DASHBOARD_GATEWAY_AUTHORIZATION (Bearer). " +
        "Mint: scripts/mint_dashboard_gateway_jwt.py; Next neu starten."
      );
    case "operator_jwt_forbidden":
      return "HTTP 403: JWT gültig, aber Rollen/Policy (GATEWAY_INSUFFICIENT_ROLES, TENANT_ID_REQUIRED, …) — gateway_roles im Mint prüfen.";
    case "operator_path_transport_failed":
      return "/health war OK, aber authentifizierte /v1-Anfrage scheitert am Netz — Proxy, MTU oder falsche API_GATEWAY_URL.";
    case "operator_health_upstream_error":
      return "GET /v1/system/health liefert Fehler — Gateway-Logs und Upstreams prüfen.";
  }
}

/**
 * Lokal/Operator: zentrale Diagnose (ein Lauf) — Gateway /health, /ready, Operator-JWT-Probe.
 * Keine Secrets im Response; `rootCause` ordnet den Zustand einer konkreten Ursache zu.
 */
export async function GET() {
  const base = gatewayBaseUrl().replace(/\/$/, "");
  const hasAuth = Boolean(serverEnv.gatewayAuthorizationHeader);
  const probe = await runGatewayBootstrapProbe();
  const gatewayHealth = gatewayHealthLabel(probe);

  let gatewaySurface: Record<string, unknown> | null = null;
  if (gatewayHealth === "ok" && base.length > 0) {
    try {
      const sr = await fetch(`${base}/v1/meta/surface`, {
        cache: "no-store",
        signal: AbortSignal.timeout(4000),
      });
      if (sr.ok) {
        gatewaySurface = (await sr.json()) as Record<string, unknown>;
      }
    } catch {
      gatewaySurface = null;
    }
  }

  const operatorHealthProbe =
    hasAuth && probe.operatorHealthHttpStatus != null
      ? {
          httpStatus: probe.operatorHealthHttpStatus,
          ok: probe.rootCause === "ok",
        }
      : null;

  const operatorHealthErrorSnippet =
    probe.rootCause !== "ok" ? probe.operatorHealthErrorSnippet : null;

  const edgeDiagnostic = edgeDiagnosticFromRootCause(probe.rootCause);
  /** Ein Lauf = eine Referenz fuer Support (Logs/ Tickets), ohne PII. */
  const supportReference = randomUUID();

  const gatewayAuthFailureCode = probe.operatorGatewayAuthCode;
  const gatewayAuthFailureHint = probe.operatorGatewayAuthHint;

  return NextResponse.json({
    apiGatewayUrl: serverEnv.apiGatewayUrl,
    gatewayAuthorizationConfigured: hasAuth,
    /** Build-Zeit-Flag (NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY); sensible /v1-Pfade laufen serverseitig. */
    useServerAdminProxy: publicEnv.useServerAdminProxy,
    /** Immer true: kein Operator-JWT im Client-Bundle, nur BFF traegt DASHBOARD_GATEWAY_AUTHORIZATION. */
    bffV1ProxyServerOnly: true,
    edgeDiagnostic,
    rootCause: probe.rootCause,
    blocksV1Reads: probe.blocksV1Reads,
    gatewayReady: probe.gatewayReadyFlag,
    gatewayReadySummary: probe.gatewayReadySummary,
    gatewayHealth,
    gatewayHttpStatus: probe.gatewayHealthHttpStatus,
    gatewaySurface,
    operatorHealthProbe,
    operatorHealthErrorSnippet:
      operatorHealthProbe && !operatorHealthProbe.ok
        ? operatorHealthErrorSnippet
        : null,
    errorMessage: probe.rootCause !== "ok" ? probe.detail : null,
    hint: edgeHint(probe),
    /** Gateway detail.code bei 401/403 der Operator-Probe (kein Secret). */
    gatewayAuthFailureCode,
    gatewayAuthFailureHint,
    supportReference,
  });
}
