import type { ProductMessage } from "@/lib/product-messages/schema";
import type { SelfHealingSnapshot } from "@/lib/self-healing/schema";

import type { SituationExplainSections } from "./types";

/**
 * Schlanker, lesbarer Kontext für POST /api/dashboard/llm/operator-explain.
 * Keine Geheimnisse — nur bereits sichtbare Diagnosefakten.
 */
export function buildSituationOperatorExplainContext(
  snap: SelfHealingSnapshot,
  deterministic: SituationExplainSections,
): Record<string, unknown> {
  const incidents = snap.incidents.slice(0, 12).map((i) => ({
    id: i.id,
    severity: i.severity,
    headline: i.headline,
    suspected_cause: i.suspectedCause.slice(0, 400),
    impact: i.impact.slice(0, 400),
    next_step: i.nextStep.slice(0, 400),
    manual_required: i.manualRemediationRequired,
    auto_remediations: [...i.autoRemediations].slice(0, 6),
  }));

  const components = snap.components
    .filter((c) => c.status !== "ok")
    .slice(0, 16)
    .map((c) => ({
      id: c.id,
      status: c.status,
      suspected_cause: c.suspectedCause.slice(0, 320),
      impact: c.impact.slice(0, 320),
      next_step: c.nextStep.slice(0, 320),
      manual_required: c.manualRemediationRequired,
    }));

  return {
    kind: "situation_explain_v1",
    collected_at_ms: snap.collected_at_ms,
    support_reference: snap.support_reference,
    health_load_error: snap.health_load_error,
    edge_blocks_v1_reads: snap.edge_blocks_v1_reads,
    edge_root_cause: snap.edge_root_cause.slice(0, 500),
    narrative_facts: snap.narrative_facts,
    deterministic_summary: {
      problem_plain: deterministic.problemPlain.slice(0, 2000),
      technical_cause: deterministic.technicalCause.slice(0, 2000),
      why_it_matters: deterministic.whyItMatters.slice(0, 1500),
      affected_areas: deterministic.affectedAreas.slice(0, 1000),
      app_already_tried: deterministic.appAlreadyTried.slice(0, 1500),
      next_recommended: deterministic.nextRecommended.slice(0, 1500),
      self_heal_vs_manual: deterministic.selfHealVsManual.slice(0, 1000),
      has_uncertainty: deterministic.hasUncertainty,
    },
    incidents,
    components_non_ok: components,
  };
}

export function buildProductMessageSituationExplainContext(
  message: ProductMessage,
  deterministic: SituationExplainSections,
): Record<string, unknown> {
  return {
    kind: "situation_explain_product_message_v1",
    message: {
      id: message.id,
      dedupe_key: message.dedupeKey,
      severity: message.severity,
      area: message.areaLabel,
      headline: message.headline.slice(0, 400),
      summary: message.summary.slice(0, 800),
      impact: message.impact.slice(0, 600),
      urgency: message.urgency.slice(0, 300),
      app_doing: message.appDoing.slice(0, 600),
      user_action: message.userAction.slice(0, 600),
      technical_excerpt: message.technicalDetail.slice(0, 800),
    },
    deterministic_summary: {
      problem_plain: deterministic.problemPlain.slice(0, 2000),
      technical_cause: deterministic.technicalCause.slice(0, 2000),
      why_it_matters: deterministic.whyItMatters.slice(0, 1500),
      affected_areas: deterministic.affectedAreas.slice(0, 1000),
      app_already_tried: deterministic.appAlreadyTried.slice(0, 1500),
      next_recommended: deterministic.nextRecommended.slice(0, 1500),
      self_heal_vs_manual: deterministic.selfHealVsManual.slice(0, 1000),
      has_uncertainty: deterministic.hasUncertainty,
    },
  };
}

export function buildSurfaceSituationExplainContext(input: {
  surfaceId: string;
  messageBaseKey: string;
  contextOverlay: Record<string, unknown>;
  deterministic: SituationExplainSections;
}): Record<string, unknown> {
  return {
    kind: "situation_explain_surface_v1",
    surface_id: input.surfaceId,
    message_base_key: input.messageBaseKey,
    context_overlay: input.contextOverlay,
    deterministic_summary: {
      problem_plain: input.deterministic.problemPlain.slice(0, 2000),
      technical_cause: input.deterministic.technicalCause.slice(0, 2000),
      why_it_matters: input.deterministic.whyItMatters.slice(0, 1500),
      affected_areas: input.deterministic.affectedAreas.slice(0, 1000),
      app_already_tried: input.deterministic.appAlreadyTried.slice(0, 1500),
      next_recommended: input.deterministic.nextRecommended.slice(0, 1500),
      self_heal_vs_manual: input.deterministic.selfHealVsManual.slice(0, 1000),
      has_uncertainty: input.deterministic.hasUncertainty,
    },
  };
}
