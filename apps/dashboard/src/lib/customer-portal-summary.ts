import { requireOperatorGatewayAuth } from "@/lib/gateway-bff";
import {
  fetchGatewayUpstream,
  GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS,
} from "@/lib/gateway-upstream-fetch";
import { serverEnv } from "@/lib/server-env";

/** BFF-Abdeckung: `/v1/commerce/customer` → dieses Zusammenfassungsmodell. */
export type CustomerPortalBffDataState = "ok" | "degraded" | "not_configured" | "backend_unavailable";

export type CustomerMeRedacted = {
  readonly schemaVersion: string;
  readonly tenantIdMasked: string;
  readonly profile: {
    displayName: string | null;
  };
  readonly plan: {
    planId: string | null;
    displayName: string | null;
    transparencyNote: string | null;
  };
  readonly tenantBudgetCapUsdMonth: string | null;
  readonly accessMatrix: Readonly<Record<string, boolean>>;
  readonly telegram: {
    connected: boolean;
    consoleTelegramRequired: boolean;
    migrationRequired?: boolean;
  };
};

export type CustomerLifecycleRedacted = Readonly<{
  schemaVersion: string;
  status: string;
  titleDe: string;
  emailVerified: boolean;
  trial: {
    durationDays: number;
    startedAt: string | null;
    endsAt: string | null;
    clockActive: boolean;
  };
  capabilities: Readonly<Record<string, boolean>>;
  gatesPreview: Readonly<Record<string, boolean>>;
}>;

export type CustomerIntegrationsRedacted = {
  readonly tenantIdMasked: string;
  readonly brokerState: string;
  readonly brokerHintPublic: string | null;
  readonly telegramState: string;
  readonly telegramHintPublic: string | null;
  /** Gateway-Hinweis-Objekt — nur oeffentliche Keys, kein API-Key. */
  readonly bitgetEnv: Readonly<Record<string, unknown>> | null;
};

export type CustomerPortalSummary = {
  /** ISO-8601 */
  readonly fetchedAt: string;
  /** Aggregat fuer Oberflächen, ohne Erfolg vorzutäuschen. */
  readonly dataState: CustomerPortalBffDataState;
  /** Kein BFF, kein Gateway, oder fehlendes DASHBOARD_GATEWAY_AUTHORIZATION. */
  readonly notConfiguredReason: "api_gateway_url_missing" | "gateway_bff_auth_missing" | null;
  readonly commerceCustomerMe: {
    httpStatus: number;
    body: CustomerMeRedacted | null;
  } | null;
  readonly commerceLifecycle: {
    httpStatus: number;
    body: CustomerLifecycleRedacted | null;
  } | null;
  readonly commerceIntegrations: {
    httpStatus: number;
    body: CustomerIntegrationsRedacted | null;
  } | null;
  /**
   * Echter Read-only-Handelssignale-Endpunkt ist (Stand Prompt 06) noch nicht angebunden;
   * nie als Production-Pass ausweisen.
   */
  readonly tradingReadonly: {
    readonly dataState: "not_configured";
    readonly code: "NO_BFF_SIGNAL_SUMMARY_ENDPOINT";
  };
  readonly errorHint: string | null;
};

function isRecord(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

function toStr(x: unknown): string | null {
  if (x == null) return null;
  if (typeof x === "string" || typeof x === "number" || typeof x === "boolean")
    return String(x);
  return null;
}

/** Liefert geparste Antworten oder null, nie Roh-Secret-Felder. */
export function redactCustomerMeJson(
  raw: unknown,
): CustomerMeRedacted | null {
  if (!isRecord(raw)) return null;
  const schemaVersion = toStr(raw["schema_version"]) ?? "unknown";
  const tenant = isRecord(raw["tenant"]) ? raw["tenant"] : null;
  const tenantIdMasked = tenant ? toStr(tenant["id_masked"]) : null;
  if (!tenantIdMasked) return null;
  const profileObj = isRecord(raw["profile"]) ? raw["profile"] : null;
  const planObj = isRecord(raw["plan"]) ? raw["plan"] : null;
  const tenantState = isRecord(raw["tenant_state"]) ? raw["tenant_state"] : null;
  const access = isRecord(raw["access"]) ? raw["access"] : null;
  const accessMatrix: Record<string, boolean> = {};
  if (access) {
    for (const [k, v] of Object.entries(access)) {
      if (typeof v === "boolean") accessMatrix[k] = v;
    }
  }
  const tel = isRecord(raw["telegram"]) ? raw["telegram"] : null;
  return {
    schemaVersion,
    tenantIdMasked,
    profile: {
      displayName: profileObj
        ? (toStr(profileObj["display_name"] ?? profileObj["displayName"]) as string | null)
        : null,
    },
    plan: {
      planId: planObj ? toStr(planObj["plan_id"] ?? planObj["planId"]) : null,
      displayName: planObj ? toStr(planObj["display_name"] ?? planObj["displayName"]) : null,
      transparencyNote: planObj
        ? toStr(
            planObj["transparency_note"] ?? planObj["transparencyNote"],
          )
        : null,
    },
    tenantBudgetCapUsdMonth: tenantState
      ? toStr(
          tenantState["budget_cap_usd_month"] ?? tenantState["budgetCapUsdMonth"],
        )
      : null,
    accessMatrix,
    telegram: {
      connected: Boolean(tel?.["connected"]),
      consoleTelegramRequired: Boolean(
        tel?.["console_telegram_required"] ?? tel?.["consoleTelegramRequired"],
      ),
      migrationRequired:
        typeof tel?.["migration_required"] === "boolean"
          ? tel.migration_required
          : undefined,
    },
  };
}

export function redactLifecycleJson(
  raw: unknown,
): CustomerLifecycleRedacted | null {
  if (!isRecord(raw)) return null;
  if (toStr(raw["status"]) == null) return null;
  const trial = isRecord(raw["trial"]) ? raw["trial"] : null;
  const caps = isRecord(raw["capabilities"])
    ? raw["capabilities"]
    : {};
  const gates = isRecord(raw["gates_preview"])
    ? raw["gates_preview"]
    : {};
  const outCaps: Record<string, boolean> = {};
  for (const [k, v] of Object.entries(caps)) {
    if (typeof v === "boolean") outCaps[k] = v;
  }
  const outGates: Record<string, boolean> = {};
  for (const [k, v] of Object.entries(gates)) {
    if (typeof v === "boolean") outGates[k] = v;
  }
  return {
    schemaVersion:
      toStr(raw["schema_version"]) ?? "tenant-lifecycle-v1",
    status: toStr(raw["status"]) ?? "unknown",
    titleDe: toStr(raw["title_de"] ?? raw["titleDe"]) ?? "",
    emailVerified: Boolean(
      raw["email_verified"] ?? raw["emailVerified"],
    ),
    trial: {
      durationDays:
        typeof trial?.["duration_days"] === "number"
          ? trial["duration_days"]
          : 0,
      startedAt: trial ? toStr(trial["started_at"] ?? trial["startedAt"]) : null,
      endsAt: trial ? toStr(trial["ends_at"] ?? trial["endsAt"]) : null,
      clockActive: Boolean(
        trial?.["clock_active"] ?? trial?.["clockActive"],
      ),
    },
    capabilities: outCaps,
    gatesPreview: outGates,
  };
}

export function redactIntegrationsJson(
  raw: unknown,
): CustomerIntegrationsRedacted | null {
  if (!isRecord(raw)) return null;
  const integ = isRecord(raw["integration"]) ? raw["integration"] : null;
  const b = isRecord(raw["bitget_env"])
    ? raw["bitget_env"]
    : null;
  if (!integ) return null;
  const bitgetEnv: Record<string, unknown> = {};
  if (b) {
    for (const [k, v] of Object.entries(b)) {
      if (!/secret|key|api_key|apikey|password|token/i.test(k)) {
        bitgetEnv[k] = v;
      }
    }
  }
  return {
    tenantIdMasked: toStr(raw["tenant_id_masked"]) ?? "—",
    brokerState: toStr(
      integ["broker_state"] ?? integ["brokerState"],
    ) ?? "unknown",
    brokerHintPublic: toStr(
      integ["broker_hint_public"] ?? integ["brokerHintPublic"],
    ),
    telegramState: toStr(
      integ["telegram_state"] ?? integ["telegramState"],
    ) ?? "unknown",
    telegramHintPublic: toStr(
      integ["telegram_hint_public"] ?? integ["telegramHintPublic"],
    ),
    bitgetEnv: Object.keys(bitgetEnv).length ? bitgetEnv : null,
  };
}

async function parseJsonBody(res: Response): Promise<unknown> {
  const t = res.headers.get("content-type") ?? "";
  if (!t.toLowerCase().includes("json")) {
    return null;
  }
  const text = await res.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/**
 * Server-only: Sichere, redigierte Sicht; keine Browser-Secrets.
 * BFF-Auth ist serverseitig; Tenant/Claims kommen aus dem Gateway-JWT, nicht aus dem Endnutzer-Cookie
 * in diesem Schritt (Produktluecke, siehe Doku).
 */
export async function getCustomerPortalSummary(): Promise<CustomerPortalSummary> {
  const fetchedAt = new Date().toISOString();
  const noTradeStub = {
    dataState: "not_configured" as const,
    code: "NO_BFF_SIGNAL_SUMMARY_ENDPOINT" as const,
  };

  if (!serverEnv.apiGatewayUrl) {
    return {
      fetchedAt,
      dataState: "not_configured",
      notConfiguredReason: "api_gateway_url_missing",
      commerceCustomerMe: null,
      commerceLifecycle: null,
      commerceIntegrations: null,
      tradingReadonly: noTradeStub,
      errorHint:
        "API_GATEWAY_URL fehlt auf dem Server — Kunden-BFF kann nicht wählen, welcher Tenant sichtbar ist.",
    };
  }

  const auth = requireOperatorGatewayAuth();
  if (!auth.ok) {
    return {
      fetchedAt,
      dataState: "not_configured",
      notConfiguredReason: "gateway_bff_auth_missing",
      commerceCustomerMe: null,
      commerceLifecycle: null,
      commerceIntegrations: null,
      tradingReadonly: noTradeStub,
      errorHint:
        "DASHBOARD_GATEWAY_AUTHORIZATION fehlt; serverseitiger BFF-Proxy zum API-Gateway ist nicht konfiguriert.",
    };
  }

  const a = auth.authorization;
  const timeout = GATEWAY_UPSTREAM_TIMEOUT_COMMERCE_MS;
  const paths = [
    { key: "me" as const, p: "/v1/commerce/customer/me" },
    { key: "lifecycle" as const, p: "/v1/commerce/customer/lifecycle/me" },
    { key: "integrations" as const, p: "/v1/commerce/customer/integrations" },
  ];
  const results: Record<string, { res: Response | null; err: string | null }> = {
    me: { res: null, err: null },
    lifecycle: { res: null, err: null },
    integrations: { res: null, err: null },
  };

  await Promise.all(
    paths.map(async ({ key, p }) => {
      try {
        const res = await fetchGatewayUpstream(p, a, { timeoutMs: timeout });
        results[key] = { res, err: null };
      } catch (e) {
        results[key] = {
          res: null,
          err: e instanceof Error ? e.message : String(e),
        };
      }
    }),
  );

  const rMe = results.me;
  const rL = results.lifecycle;
  const rI = results.integrations;

  if (rMe.res == null) {
    return {
      fetchedAt,
      dataState: "backend_unavailable",
      notConfiguredReason: null,
      commerceCustomerMe: { httpStatus: 0, body: null },
      commerceLifecycle: null,
      commerceIntegrations: null,
      tradingReadonly: noTradeStub,
      errorHint: rMe.err,
    };
  }
  if (!rMe.res.ok) {
    const u = await parseJsonBody(rMe.res);
    return {
      fetchedAt,
      dataState: "backend_unavailable",
      notConfiguredReason: null,
      commerceCustomerMe: {
        httpStatus: rMe.res.status,
        body: u ? redactCustomerMeJson(u) : null,
      },
      commerceLifecycle: null,
      commerceIntegrations: null,
      tradingReadonly: noTradeStub,
      errorHint: `customer/me HTTP ${rMe.res.status}`,
    };
  }

  const meBody = redactCustomerMeJson((await parseJsonBody(rMe.res)) ?? null);

  const lifecycleRes: NonNullable<CustomerPortalSummary["commerceLifecycle"]> =
    rL.res
      ? rL.res.ok
        ? {
            httpStatus: rL.res.status,
            body: redactLifecycleJson(
              (await parseJsonBody(rL.res)) ?? null,
            ),
          }
        : { httpStatus: rL.res.status, body: null }
      : { httpStatus: 0, body: null };

  const integRes: NonNullable<CustomerPortalSummary["commerceIntegrations"]> =
    rI.res
      ? rI.res.ok
        ? {
            httpStatus: rI.res.status,
            body: redactIntegrationsJson(
              (await parseJsonBody(rI.res)) ?? null,
            ),
          }
        : { httpStatus: rI.res.status, body: null }
      : { httpStatus: 0, body: null };

  let dataState: CustomerPortalBffDataState = "ok";
  if (!meBody) dataState = "degraded";
  if (rL.err != null || rI.err != null) dataState = "degraded";
  if (rL.res == null || rI.res == null) dataState = "degraded";
  else {
    if (!rL.res.ok) dataState = "degraded";
    if (!rI.res.ok) dataState = "degraded";
    if (rL.res.ok && lifecycleRes.body == null) dataState = "degraded";
    if (rI.res.ok && integRes.body == null) dataState = "degraded";
  }

  const hintParts: string[] = [];
  if (rL.err) hintParts.push(`lifecycle: ${rL.err}`);
  if (rI.err) hintParts.push(`integrations: ${rI.err}`);

  return {
    fetchedAt,
    dataState,
    notConfiguredReason: null,
    commerceCustomerMe: { httpStatus: rMe.res.status, body: meBody },
    commerceLifecycle: lifecycleRes,
    commerceIntegrations: integRes,
    tradingReadonly: noTradeStub,
    errorHint: hintParts.length ? hintParts.join(" | ") : null,
  };
}
