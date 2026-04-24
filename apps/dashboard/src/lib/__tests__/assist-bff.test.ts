import {
  ASSIST_DASHBOARD_SEGMENTS,
  isAssistDashboardSegment,
  isValidAssistConversationId,
} from "@/lib/assist-bff";

describe("assist-bff", () => {
  it("lists five dashboard segments", () => {
    expect(ASSIST_DASHBOARD_SEGMENTS).toHaveLength(5);
    expect(new Set(ASSIST_DASHBOARD_SEGMENTS).size).toBe(5);
  });

  it("isAssistDashboardSegment rejects unknown", () => {
    expect(isAssistDashboardSegment("admin-operations")).toBe(true);
    expect(isAssistDashboardSegment("ops-risk")).toBe(true);
    expect(isAssistDashboardSegment("evil-segment")).toBe(false);
  });

  it("isValidAssistConversationId accepts canonical UUID", () => {
    expect(
      isValidAssistConversationId("550e8400-e29b-41d4-a716-446655440000"),
    ).toBe(true);
  });

  it("isValidAssistConversationId rejects wrong length or variant", () => {
    expect(isValidAssistConversationId("not-a-uuid")).toBe(false);
    expect(
      isValidAssistConversationId("550e8400-e29b-41d4-a716-44665544000"),
    ).toBe(false);
    expect(
      isValidAssistConversationId("550e8400-e29b-41d4-a716-446655440000x"),
    ).toBe(false);
  });
});
