import { precheckPromotionRequest } from "@/lib/ai-strategy-proposal-governance";

describe("ai-strategy-proposal-governance", () => {
  it("blocks promotion without human ack", () => {
    expect(
      precheckPromotionRequest({
        lifecycleStatus: "validation_passed",
        humanAcknowledged: false,
      }).ok,
    ).toBe(false);
  });

  it("blocks promotion before validation_passed", () => {
    expect(
      precheckPromotionRequest({
        lifecycleStatus: "draft",
        humanAcknowledged: true,
      }).ok,
    ).toBe(false);
  });

  it("allows precheck when validation passed and ack", () => {
    expect(
      precheckPromotionRequest({
        lifecycleStatus: "validation_passed",
        humanAcknowledged: true,
      }).ok,
    ).toBe(true);
  });
});
