import { sortComponentsByBusinessPriority } from "@/lib/diagnostics/diagnostics-view-model";
import type {
  SelfHealingSnapshot,
} from "@/lib/self-healing/schema";
import type { SelfHealingSeverity } from "@/lib/self-healing/schema";
import type { SelfHealingIncident } from "@/lib/self-healing/schema";
import type { SelfHealingComponentRow } from "@/lib/self-healing/schema";
import type { ProductMessage } from "@/lib/product-messages/schema";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

import type { SituationExplainSections } from "./types";

export function snapshotWarrantsSituationExplain(
  snap: SelfHealingSnapshot,
): boolean {
  if (snap.health_load_error) return true;
  if (snap.edge_blocks_v1_reads) return true;
  if (snap.incidents.length > 0) return true;
  const nf = snap.narrative_facts;
  if (nf) {
    if (nf.downCount > 0 || nf.degradedCount > 0 || nf.openIncidentCount > 0) {
      return true;
    }
  }
  return snap.components.some(
    (c) => c.status === "down" || c.status === "degraded",
  );
}

const INCIDENT_RANK: Record<SelfHealingSeverity, number> = {
  info: 0,
  hint: 1,
  warning: 2,
  critical: 3,
  blocking: 4,
};

function incidentSeverityRank(s: SelfHealingSeverity): number {
  return INCIDENT_RANK[s] ?? 0;
}

function sortIncidents(
  list: readonly SelfHealingIncident[],
): SelfHealingIncident[] {
  return [...list].sort(
    (a, b) => incidentSeverityRank(b.severity) - incidentSeverityRank(a.severity),
  );
}

function joinUnique(lines: readonly string[], max: number, sep = "\n"): string {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of lines) {
    const s = raw.replace(/\s+/g, " ").trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
    if (out.length >= max) break;
  }
  return out.join(sep);
}

function clip(s: string, n: number): string {
  const t = s.trim();
  if (t.length <= n) return t;
  return `${t.slice(0, n - 1)}…`;
}

function badComponents(snap: SelfHealingSnapshot): SelfHealingComponentRow[] {
  return sortComponentsByBusinessPriority(
    snap.components.filter(
      (c) => c.status === "degraded" || c.status === "down",
    ),
  ).slice(0, 8);
}

/**
 * Baut eine ehrliche, faktenbasierte Erklärung aus Self-Healing-Snapshot
 * (Inzidente, gestörte Komponenten, Edge/Health-Fehler).
 */
export function buildDeterministicSituationExplainFromSnapshot(
  snap: SelfHealingSnapshot,
  t: TranslateFn,
): SituationExplainSections {
  const incidents = sortIncidents(snap.incidents);
  const comps = badComponents(snap);
  const hints = snap.healing_hints ?? [];

  let hasUncertainty = false;

  const problemParts: string[] = [];
  if (snap.health_load_error) {
    problemParts.push(
      t("situationAiExplain.problem.healthSnapshotFailed", {
        detail: clip(snap.health_load_error, 180),
      }),
    );
  }
  if (snap.edge_blocks_v1_reads) {
    problemParts.push(t("situationAiExplain.problem.edgeBlocksReads"));
  }
  for (const i of incidents.slice(0, 4)) {
    problemParts.push(i.headline.trim());
  }
  if (incidents.length === 0 && comps.length > 0) {
    const names = comps
      .slice(0, 5)
      .map((c) => t(c.labelKey))
      .join(", ");
    problemParts.push(
      t("situationAiExplain.problem.componentsDegraded", { list: names }),
    );
  }
  if (problemParts.length === 0) {
    problemParts.push(t("situationAiExplain.problem.noExplicitIncident"));
    hasUncertainty = true;
  }

  const techParts: string[] = [];
  if (snap.edge_root_cause?.trim()) {
    techParts.push(clip(snap.edge_root_cause.trim(), 400));
  }
  if (snap.health_load_error) {
    techParts.push(clip(snap.health_load_error, 280));
  }
  for (const i of incidents.slice(0, 5)) {
    const sc = i.suspectedCause.trim();
    const td = i.technicalDetail.trim();
    if (sc) techParts.push(clip(sc, 220));
    if (td) techParts.push(clip(td, 200));
  }
  for (const c of comps.slice(0, 4)) {
    if (c.technicalDetail.trim()) {
      techParts.push(`${t(c.labelKey)}: ${clip(c.technicalDetail.trim(), 160)}`);
    } else if (c.suspectedCause.trim()) {
      techParts.push(`${t(c.labelKey)}: ${clip(c.suspectedCause.trim(), 160)}`);
    }
  }
  if (techParts.length === 0) {
    techParts.push(t("situationAiExplain.technical.uncertain"));
    hasUncertainty = true;
  }

  const impactParts = [
    ...incidents.slice(0, 6).map((i) => i.impact.trim()),
    ...comps.slice(0, 4).map((c) => c.impact.trim()),
  ].filter(Boolean);
  const why =
    joinUnique(impactParts, 6) ||
    t("situationAiExplain.why.fallbackDegraded");

  const areas = joinUnique(
    [
      ...incidents.map((i) => t(i.areaLabelKey)),
      ...comps.map((c) => t(c.labelKey)),
    ],
    12,
    " · ",
  );

  const autoTry = [
    ...incidents.flatMap((i) => [...i.autoRemediations]),
    ...comps.flatMap((c) => [...c.autoRemediations]),
    ...hints.map((h) => t(h.messageKey)),
  ].filter((s) => s.trim().length > 0);
  const appTried =
    joinUnique(autoTry, 8) || t("situationAiExplain.appTried.noneKnown");

  const nextParts = [
    ...incidents.slice(0, 6).map((i) => i.nextStep.trim()),
    ...comps.slice(0, 4).map((c) => c.nextStep.trim()),
  ].filter(Boolean);
  const nextRec =
    joinUnique(nextParts, 6) || t("situationAiExplain.next.fallback");

  const anyManualInc = incidents.some((i) => i.manualRemediationRequired);
  const anyManualComp = comps.some((c) => c.manualRemediationRequired);
  const anyAuto =
    autoTry.length > 0 ||
    hints.length > 0 ||
    incidents.some((i) => i.autoRemediations.length > 0);

  let selfHealVsManual: string;
  if (anyManualInc || anyManualComp) {
    selfHealVsManual = t("situationAiExplain.selfHeal.manualRequired");
  } else if (anyAuto) {
    selfHealVsManual = t("situationAiExplain.selfHeal.partialAutomatic");
  } else {
    selfHealVsManual = t("situationAiExplain.selfHeal.observeAndEscalate");
    hasUncertainty = true;
  }

  return {
    problemPlain: joinUnique(problemParts, 8, "\n"),
    technicalCause: joinUnique(techParts, 10, "\n"),
    whyItMatters: why,
    affectedAreas: areas || t("situationAiExplain.areas.unknown"),
    appAlreadyTried: appTried,
    nextRecommended: nextRec,
    selfHealVsManual,
    hasUncertainty,
  };
}

/**
 * Erklärung aus einer produktreifen Meldung (Fetch-Fehler, Gateway, …).
 */
export function buildDeterministicSituationExplainFromProductMessage(
  message: ProductMessage,
  t: TranslateFn,
): SituationExplainSections {
  const tech = message.technicalDetail.trim();
  const technicalCause = tech
    ? clip(tech, 360)
    : t("situationAiExplain.technical.openTechnicalFold");

  const userAct = message.userAction.trim();
  const nextRec =
    userAct || t("situationAiExplain.next.reloadOrHealth");

  let selfHealVsManual: string;
  if (/retry|erneut|automat/i.test(message.appDoing)) {
    selfHealVsManual = t("situationAiExplain.selfHeal.retriesMayRun");
  } else if (message.appDoing.trim()) {
    selfHealVsManual = t("situationAiExplain.selfHeal.platformReported", {
      snippet: clip(message.appDoing, 200),
    });
  } else {
    selfHealVsManual = t("situationAiExplain.selfHeal.noAutoFixAssumed");
  }

  return {
    problemPlain: `${message.headline}\n${message.summary}`.trim(),
    technicalCause,
    whyItMatters: message.impact.trim() || t("situationAiExplain.why.dataOrView"),
    affectedAreas: message.areaLabel.trim(),
    appAlreadyTried: message.appDoing.trim() || t("situationAiExplain.appTried.noneStated"),
    nextRecommended: nextRec,
    selfHealVsManual,
    hasUncertainty: !tech,
  };
}

/**
 * Oberflächen-Diagnose (Chart/Terminal): nutzt bereits übersetzte Titel & Lead + Overlay-Fakten.
 */
export function buildDeterministicSituationExplainFromSurfaceBrief(
  input: Readonly<{
    title: string;
    lead: string;
    surfaceId: string;
    contextOverlay: Record<string, unknown>;
  }>,
  t: TranslateFn,
): SituationExplainSections {
  const overlayJson = JSON.stringify(input.contextOverlay, null, 0);
  const technicalCause = clip(overlayJson, 520);

  return {
    problemPlain: `${input.title}\n${input.lead}`.trim(),
    technicalCause,
    whyItMatters: t("situationAiExplain.why.surfaceTrust"),
    affectedAreas: t("situationAiExplain.areas.surface", {
      id: input.surfaceId,
    }),
    appAlreadyTried: t("situationAiExplain.appTried.surfaceClient"),
    nextRecommended: t("situationAiExplain.next.surface"),
    selfHealVsManual: t("situationAiExplain.selfHeal.surfaceMostlyManual"),
    hasUncertainty: true,
  };
}
