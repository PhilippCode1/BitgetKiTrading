import {
  guidedWelcomeUrl,
  ONBOARDING_DEFAULT_RETURN,
  ONBOARDING_NAV_HREF,
  onboardingUrlWithReturn,
} from "@/lib/onboarding-flow";

describe("onboarding-flow", () => {
  it("defaults return target to console root", () => {
    expect(ONBOARDING_DEFAULT_RETURN).toBe("/console");
  });

  it("builds onboarding URL with encoded returnTo", () => {
    expect(onboardingUrlWithReturn("/console")).toBe(
      "/onboarding?returnTo=%2Fconsole",
    );
    expect(onboardingUrlWithReturn("/console/ops")).toBe(
      "/onboarding?returnTo=%2Fconsole%2Fops",
    );
  });

  it("normalizes invalid returnTo to console root", () => {
    expect(onboardingUrlWithReturn("not-a-path")).toBe(
      "/onboarding?returnTo=%2Fconsole",
    );
  });

  it("blocks external returnTo URLs", () => {
    expect(onboardingUrlWithReturn("https://evil.example")).toBe(
      "/onboarding?returnTo=%2Fconsole",
    );
    expect(onboardingUrlWithReturn("//evil.example")).toBe(
      "/onboarding?returnTo=%2Fconsole",
    );
  });

  it("maps legacy /ops to internal console route", () => {
    expect(onboardingUrlWithReturn("/ops")).toBe(
      "/onboarding?returnTo=%2Fconsole%2Fops",
    );
  });

  it("chains welcome then onboarding", () => {
    const u = new URL(guidedWelcomeUrl("/console"), "http://localhost");
    expect(u.pathname).toBe("/welcome");
    expect(u.searchParams.get("returnTo")).toBe(
      "/onboarding?returnTo=%2Fconsole",
    );
  });

  it("exposes stable nav href for sidebar", () => {
    expect(ONBOARDING_NAV_HREF).toBe("/onboarding?returnTo=%2Fconsole");
  });
});
