import { sanitizeReturnTo } from "@/lib/return-to-safety";

describe("return-to-safety", () => {
  it("erlaubt returnTo zur Konsole", () => {
    expect(sanitizeReturnTo("/console")).toBe("/console");
    expect(sanitizeReturnTo("/console/ops?tab=risk")).toBe(
      "/console/ops?tab=risk",
    );
  });

  it("mappt legacy /ops auf interne Konsolenroute", () => {
    expect(sanitizeReturnTo("/ops")).toBe("/console/ops");
    expect(sanitizeReturnTo("/ops/live")).toBe("/console/ops/live");
  });

  it("blockiert externe returnTo URLs", () => {
    expect(sanitizeReturnTo("https://evil.example")).toBe("/console");
    expect(sanitizeReturnTo("//evil.example")).toBe("/console");
  });

  it("faellt bei leerem oder kaputtem returnTo auf Konsole zurueck", () => {
    expect(sanitizeReturnTo("")).toBe("/console");
    expect(sanitizeReturnTo("not-a-path")).toBe("/console");
    expect(sanitizeReturnTo("/")).toBe("/console");
  });
});
