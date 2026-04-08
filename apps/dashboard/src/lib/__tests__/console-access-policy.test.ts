import {
  consoleRouteRequiresOperatorShell,
  isAdminSafetyConsolePath,
  isMarketingPublicRoute,
} from "@/lib/console-access-policy";
import { CONSOLE_BASE } from "@/lib/console-paths";

describe("console-access-policy", () => {
  it("treats root as marketing public", () => {
    expect(isMarketingPublicRoute("/")).toBe(true);
    expect(isMarketingPublicRoute("/console")).toBe(false);
  });

  it("detects operator shell paths", () => {
    expect(consoleRouteRequiresOperatorShell("/")).toBe(false);
    expect(consoleRouteRequiresOperatorShell(CONSOLE_BASE)).toBe(true);
    expect(consoleRouteRequiresOperatorShell(`${CONSOLE_BASE}/ops`)).toBe(true);
  });

  it("detects admin safety console path", () => {
    expect(isAdminSafetyConsolePath(`${CONSOLE_BASE}/admin`)).toBe(true);
    expect(isAdminSafetyConsolePath(`${CONSOLE_BASE}/admin/extra`)).toBe(true);
    expect(isAdminSafetyConsolePath(`${CONSOLE_BASE}/ops`)).toBe(false);
  });
});
