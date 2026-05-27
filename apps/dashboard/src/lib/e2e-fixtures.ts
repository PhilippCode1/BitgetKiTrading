import { cookies } from "next/headers";

/** HttpOnly-Cookie fuer E2E: Live-Ribbon ohne laufendes Gateway mocken. */
export const E2E_LIVE_RIBBON_COOKIE = "e2e_fixture_live_ribbon";

function e2eFixturesEnabled(): boolean {
  if ((process.env.NODE_ENV ?? "").toLowerCase() === "production") {
    return false;
  }
  const flag = (process.env.ENABLE_E2E_FIXTURES ?? "").trim().toLowerCase();
  return flag === "true" || flag === "1";
}

/** Nur Dev/E2E: Ribbon-Test ohne Gateway-Seed. */
export async function readE2eLiveRibbonFixture(): Promise<boolean> {
  if (!e2eFixturesEnabled()) {
    return false;
  }
  const jar = await cookies();
  return jar.get(E2E_LIVE_RIBBON_COOKIE)?.value === "1";
}
