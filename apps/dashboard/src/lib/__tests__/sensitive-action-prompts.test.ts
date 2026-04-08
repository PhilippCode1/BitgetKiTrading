import {
  adminRulesSaveConfirmMessage,
  strategyLifecycleConfirmMessage,
} from "@/lib/sensitive-action-prompts";

describe("sensitive-action-prompts", () => {
  it("admin rules message mentions save impact", () => {
    const m = adminRulesSaveConfirmMessage();
    expect(m).toMatch(/speichern/i);
    expect(m.length).toBeGreaterThan(40);
  });

  it("lifecycle messages are specific per status", () => {
    expect(strategyLifecycleConfirmMessage("promoted")).toMatch(/PROMOTED/i);
    expect(strategyLifecycleConfirmMessage("retired")).toMatch(/RETIRED/i);
    expect(strategyLifecycleConfirmMessage("unknown")).toMatch(/unknown/i);
  });
});
