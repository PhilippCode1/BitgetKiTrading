import { isSafetyDiagnosisSuccessPayload } from "@/lib/safety-diagnosis-errors";

describe("isSafetyDiagnosisSuccessPayload", () => {
  it("accepts payload with authority none", () => {
    expect(
      isSafetyDiagnosisSuccessPayload({
        ok: true,
        result: {
          incident_summary_de: "Kurztext",
          execution_authority: "none",
        },
      }),
    ).toBe(true);
  });

  it("rejects payload without authority none", () => {
    expect(
      isSafetyDiagnosisSuccessPayload({
        ok: true,
        result: {
          incident_summary_de: "Kurztext",
          execution_authority: "operator",
        },
      }),
    ).toBe(false);
  });
});
