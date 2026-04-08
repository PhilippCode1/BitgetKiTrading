import type { GatewayReadEnvelope } from "@bitget-btc-ai/shared-ts";

import type { ProductMessage, ProductMessageSeverity } from "./schema";

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | boolean>,
) => string;

function severityForGateway(
  status: GatewayReadEnvelope["status"],
  empty: boolean,
): ProductMessageSeverity {
  if (status === "degraded") return "warning";
  if (empty && status === "ok") return "hint";
  return "info";
}

/**
 * Gateway-Lesenvelope → eine produktreife Meldung (oder null bei ok ohne Hinweis).
 */
export function buildProductMessageFromGatewayEnvelope(
  payload: GatewayReadEnvelope,
  t: TranslateFn,
): ProductMessage | null {
  const degraded = payload.status === "degraded";
  const emptyHint = Boolean(payload.message && payload.empty_state);

  if (!degraded && !emptyHint) return null;

  const headline =
    (payload.message && payload.message.trim()) ||
    t("console.gatewayEnvelope.degradedGeneric");

  const reason = (payload.degradation_reason ?? "").trim();
  const next = (payload.next_step ?? "").trim();

  const summary = degraded
    ? reason
      ? t("productMessage.gateway.summaryWithReason", { reason })
      : t("productMessage.gateway.summaryDegraded")
    : t("productMessage.gateway.summaryEmptyState");

  const impact = degraded
    ? t("productMessage.gateway.impactDegraded")
    : t("productMessage.gateway.impactEmpty");

  const urgency = degraded
    ? t("productMessage.gateway.urgencyDegraded")
    : t("productMessage.gateway.urgencyHint");

  const appDoing = t("productMessage.gateway.appDoing");

  const userAction = next
    ? t("productMessage.gateway.userActionWithStep", { step: next })
    : t("productMessage.gateway.userActionDefault");

  const technicalDetail = JSON.stringify(
    {
      status: payload.status,
      message: payload.message,
      empty_state: payload.empty_state,
      degradation_reason: payload.degradation_reason,
      next_step: payload.next_step,
      read_envelope_contract_version: payload.read_envelope_contract_version,
    },
    null,
    2,
  );

  const dedupeKey = `gateway-read:${payload.status}:${reason || headline.slice(0, 80)}`;

  return {
    id: `gateway-envelope:${dedupeKey}`,
    dedupeKey,
    severity: severityForGateway(payload.status, payload.empty_state),
    areaLabel: t("productMessage.area.apiData"),
    headline,
    summary,
    impact,
    urgency,
    appDoing,
    userAction,
    technicalDetail,
  };
}
