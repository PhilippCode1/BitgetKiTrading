import type { SelfHealingSnapshot } from "@/lib/self-healing/schema";
import type { ProductMessage } from "@/lib/product-messages/schema";

import {
  buildDeterministicSituationExplainFromProductMessage,
  buildDeterministicSituationExplainFromSnapshot,
  snapshotWarrantsSituationExplain,
} from "../build-deterministic";

const t = (
  key: string,
  vars?: Record<string, string | number | boolean>,
): string => {
  if (!vars) return key;
  return `${key}|${Object.entries(vars)
    .map(([k, v]) => `${k}=${v}`)
    .join(",")}`;
};

function baseSnap(
  patch: Partial<SelfHealingSnapshot> = {},
): SelfHealingSnapshot {
  const s: SelfHealingSnapshot = {
    schema_version: 1,
    collected_at_ms: 1_700_000_000_000,
    support_reference: null,
    health_load_error: null,
    edge_root_cause: "",
    edge_blocks_v1_reads: false,
    components: [],
    incidents: [],
    healing_hints: [],
    not_auto_fixable: [],
    narrative_facts: {
      aggregateLevel: "green",
      healthyCount: 2,
      degradedCount: 0,
      downCount: 0,
      notConfiguredCount: 0,
      openIncidentCount: 0,
      edgeBlocksReads: false,
      worstComponentIds: [],
    },
    ...patch,
  };
  return s;
}

describe("snapshotWarrantsSituationExplain", () => {
  it("false when green and no incidents", () => {
    expect(snapshotWarrantsSituationExplain(baseSnap())).toBe(false);
  });

  it("true when health_load_error", () => {
    expect(
      snapshotWarrantsSituationExplain(
        baseSnap({ health_load_error: "econnrefused" }),
      ),
    ).toBe(true);
  });

  it("true when degradedCount > 0", () => {
    expect(
      snapshotWarrantsSituationExplain(
        baseSnap({
          narrative_facts: {
            aggregateLevel: "degraded",
            healthyCount: 1,
            degradedCount: 1,
            downCount: 0,
            notConfiguredCount: 0,
            openIncidentCount: 0,
            edgeBlocksReads: false,
            worstComponentIds: ["redis"],
          },
        }),
      ),
    ).toBe(true);
  });
});

describe("buildDeterministicSituationExplainFromSnapshot", () => {
  it("includes health load error in problemPlain", () => {
    const ex = buildDeterministicSituationExplainFromSnapshot(
      baseSnap({ health_load_error: "timeout" }),
      t,
    );
    expect(ex.problemPlain).toContain("situationAiExplain.problem.healthSnapshotFailed");
    expect(ex.hasUncertainty).toBe(true);
  });

  it("merges incident headlines", () => {
    const ex = buildDeterministicSituationExplainFromSnapshot(
      baseSnap({
        incidents: [
          {
            id: "i1",
            dedupeKey: "k1",
            severity: "warning",
            areaLabelKey: "pages.selfHealing.area.gateway",
            headline: "Gateway slow",
            startedAtMs: null,
            lastSeenMs: 1,
            suspectedCause: "queue",
            technicalDetail: "detail",
            impact: "reads slow",
            autoRemediations: ["retry"],
            nextStep: "check logs",
            manualRemediationRequired: false,
            componentId: null,
            repairLogKey: null,
          },
        ],
      }),
      t,
    );
    expect(ex.problemPlain).toContain("Gateway slow");
    expect(ex.whyItMatters).toContain("reads slow");
  });
});

describe("buildDeterministicSituationExplainFromProductMessage", () => {
  it("maps product fields", () => {
    const msg: ProductMessage = {
      id: "x",
      dedupeKey: "d",
      severity: "warning",
      areaLabel: "API",
      headline: "H",
      summary: "S",
      impact: "I",
      urgency: "U",
      appDoing: "retrying",
      userAction: "reload",
      technicalDetail: "HTTP 502",
    };
    const ex = buildDeterministicSituationExplainFromProductMessage(msg, t);
    expect(ex.problemPlain).toContain("H");
    expect(ex.nextRecommended).toContain("reload");
    expect(ex.hasUncertainty).toBe(false);
  });
});
