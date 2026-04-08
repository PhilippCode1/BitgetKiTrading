import { buildSelfHealingSnapshot } from "../build-snapshot";
import type { SelfHealingRawInputs } from "../build-snapshot";

const t = (key: string, vars?: Record<string, string | number | boolean>) => {
  if (vars) {
    let s = key;
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
    return s;
  }
  return key;
};

describe("buildSelfHealingSnapshot", () => {
  it("liefert alle Registry-Komponenten und narrative_facts", () => {
    const raw: SelfHealingRawInputs = {
      collected_at_ms: 1_700_000_000_000,
      support_reference: "ref-1",
      health: null,
      health_load_error: null,
      probe: {
        rootCause: "ok",
        blocksV1Reads: false,
        detail: "",
        gatewayHealthHttpStatus: 200,
        gatewayReadyFlag: true,
        gatewayReadySummary: null,
        operatorHealthHttpStatus: 200,
        operatorHealthErrorSnippet: null,
        operatorGatewayAuthCode: null,
        operatorGatewayAuthHint: null,
      },
      open_alerts: [],
      outbox_items: [],
    };
    const snap = buildSelfHealingSnapshot(raw, t);
    expect(snap.schema_version).toBe(1);
    expect(snap.components.length).toBeGreaterThan(25);
    expect(snap.narrative_facts).toBeDefined();
    expect(snap.healing_hints.length).toBeGreaterThan(0);
  });

  it("markiert Health-Ladefehler als blocking Incident", () => {
    const raw: SelfHealingRawInputs = {
      collected_at_ms: 1_700_000_000_000,
      support_reference: null,
      health: null,
      health_load_error: "ECONNREFUSED",
      probe: {
        rootCause: "gateway_unreachable",
        blocksV1Reads: true,
        detail: "down",
        gatewayHealthHttpStatus: null,
        gatewayReadyFlag: null,
        gatewayReadySummary: null,
        operatorHealthHttpStatus: null,
        operatorHealthErrorSnippet: null,
        operatorGatewayAuthCode: null,
        operatorGatewayAuthHint: null,
      },
      open_alerts: [],
      outbox_items: [],
    };
    const snap = buildSelfHealingSnapshot(raw, t);
    const hi = snap.incidents.find((i) => i.id === "inc:health_load");
    expect(hi?.severity).toBe("blocking");
  });
});
