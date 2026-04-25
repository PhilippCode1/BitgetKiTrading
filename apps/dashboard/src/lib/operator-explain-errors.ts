/**
 * Nutzerfreundliche Fehlertexte fuer den Operator-Explain-Flow (ohne Rohtext aus Upstreams).
 */

import { formatApiErrorDetail } from "@/lib/api-error-detail";

export type OperatorExplainDetailFields = {
  code: string | null;
  message: string | null;
  failure_class: string | null;
};

export function extractDetailFields(
  bodyText: string,
): OperatorExplainDetailFields {
  try {
    const j = JSON.parse(bodyText) as Record<string, unknown>;
    const d = j.detail;
    if (typeof d === "object" && d !== null && !Array.isArray(d)) {
      const o = d as Record<string, unknown>;
      const code = typeof o.code === "string" ? o.code : null;
      const message = typeof o.message === "string" ? o.message : null;
      const failure_class =
        typeof o.failure_class === "string" ? o.failure_class : null;
      return { code, message, failure_class };
    }
    const err = j.error;
    if (typeof err === "object" && err !== null && !Array.isArray(err)) {
      const o = err as Record<string, unknown>;
      const code = typeof o.code === "string" ? o.code : null;
      const message = typeof o.message === "string" ? o.message : null;
      return { code, message, failure_class: null };
    }
  } catch {
    /* ignore */
  }
  return { code: null, message: null, failure_class: null };
}

/** Kuerzt und saubert Text fuer die UI (keine Romane, keine Stacktrace-Zeilen). */
export function sanitizePublicErrorMessage(raw: string, maxLen = 220): string {
  let s = raw.replace(/\s+/g, " ").trim();
  s = s.replace(/authorization\s*[:=]\s*bearer\s+\S+/gi, "authorization=***");
  s = s.replace(/\b(bearer|token|secret|api[_-]?key|password)\s*[:=]\s*\S+/gi, "$1=***");
  if (/^\s*at\s+/.test(s) || /\bat\s+\w+\s*\(/.test(s)) {
    return "";
  }
  if (s.length > maxLen) {
    s = `${s.slice(0, maxLen - 1)}…`;
  }
  return s;
}

export function resolveOperatorExplainFailure(
  status: number,
  bodyText: string,
  t: (key: string, vars?: Record<string, string | number | boolean>) => string,
): string {
  const trimmed = bodyText.trim();
  if (trimmed.startsWith("<!") || trimmed.startsWith("<html")) {
    return t("pages.health.aiExplainErrUnexpectedHtml");
  }

  const { code, message, failure_class } = extractDetailFields(bodyText);
  const lower = `${message ?? ""} ${bodyText}`.toLowerCase();

  if (status === 413 || code === "PROMPT_TOO_LARGE") {
    return t("pages.health.aiExplainErrPayloadTooLarge");
  }

  if (status === 400 && code === "CONTEXT_JSON_TOO_LARGE") {
    return t("pages.health.aiExplainErrContextTooLarge");
  }

  if (status === 401) {
    return t("pages.health.aiExplainErrAuth");
  }

  if (status === 429) {
    return t("pages.health.aiExplainErrRateLimit");
  }

  if (status === 503) {
    if (
      code === "LLM_ORCH_UNAVAILABLE" ||
      lower.includes("internal_api_key") ||
      lower.includes("llm_orch")
    ) {
      return t("pages.health.aiExplainErrOrchestratorConfig");
    }
    if (
      lower.includes("dashboard_gateway_authorization") ||
      lower.includes("gateway:read") ||
      lower.includes("bearer-jwt")
    ) {
      return t("pages.health.aiExplainErrBffAuth");
    }
    return t("pages.health.aiExplainErrServiceUnavailable");
  }

  if (status === 502) {
    if (failure_class === "circuit_open") {
      return t("pages.health.aiExplainErrCircuitOpen");
    }
    if (failure_class === "no_provider_configured") {
      return t("pages.health.aiExplainErrProviderNotConfigured");
    }
    if (
      lower.includes("openai_api_key") ||
      (lower.includes("openai") && lower.includes("key"))
    ) {
      return t("pages.health.aiExplainErrOpenaiKey");
    }
    if (code === "LLM_UNAVAILABLE" || lower.includes("llm_unavailable")) {
      if (failure_class === "retry_exhausted") {
        return t("pages.health.aiExplainErrLlmRetryExhausted");
      }
      return t("pages.health.aiExplainErrLlmUnavailable");
    }
    return t("pages.health.aiExplainErrBadGateway");
  }

  if (status === 400 && code === "QUESTION_TOO_LONG") {
    return t("pages.health.aiExplainErrQuestionLong");
  }

  if (status >= 500) {
    return t("pages.health.aiExplainErrServer");
  }

  const detail = sanitizePublicErrorMessage(formatApiErrorDetail(bodyText));
  if (!detail) {
    return t("pages.health.aiExplainErrGeneric", { status });
  }
  return `${t("pages.health.aiExplainErrPrefix")} ${detail}`;
}

export function resolveNetworkFailure(
  err: unknown,
  t: (key: string, vars?: Record<string, string | number | boolean>) => string,
): string | null {
  if (!(err instanceof Error)) {
    return null;
  }
  const m = err.message.toLowerCase();
  if (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("load failed")
  ) {
    return t("pages.health.aiExplainErrOffline");
  }
  if (m.includes("econnrefused") || m.includes("connection refused")) {
    return t("pages.health.aiExplainErrOffline");
  }
  return null;
}

export function isOperatorExplainSuccessPayload(parsed: unknown): parsed is {
  result: { explanation_de?: string; execution_authority?: string };
  ok?: boolean;
} {
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return false;
  }
  const p = parsed as Record<string, unknown>;
  if (p.ok === false) {
    return false;
  }
  const r = p.result;
  if (r === null || typeof r !== "object" || Array.isArray(r)) {
    return false;
  }
  const ro = r as Record<string, unknown>;
  const ex = ro.explanation_de;
  const authority = ro.execution_authority;
  return (
    typeof ex === "string" &&
    ex.trim().length > 0 &&
    authority === "none"
  );
}
