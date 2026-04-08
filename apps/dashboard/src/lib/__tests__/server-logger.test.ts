import { redactForLog } from "@/lib/server-logger";

describe("redactForLog", () => {
  it("redacts sensitive keys case-insensitively", () => {
    const out = redactForLog({
      message: "ok",
      Authorization: "Bearer secret",
      nested: { Cookie: "a=b" },
    }) as Record<string, unknown>;
    expect(out.Authorization).toBe("[REDACTED]");
    expect((out.nested as Record<string, unknown>).Cookie).toBe("[REDACTED]");
    expect(out.message).toBe("ok");
  });
});
