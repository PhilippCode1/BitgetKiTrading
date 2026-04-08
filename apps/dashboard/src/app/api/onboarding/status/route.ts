import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  DASHBOARD_PREF_COOKIE_MAX_AGE,
  defaultUiModeForOnboarding,
  ONBOARDING_COOKIE_NAME,
  type OnboardingStatus,
  UI_MODE_COOKIE_NAME,
} from "@/lib/dashboard-prefs";

function settledStatus(v: string | undefined): OnboardingStatus | null {
  return v === "complete" || v === "skipped" ? v : null;
}

function applyOnboardingCookies(
  res: NextResponse,
  status: OnboardingStatus,
): void {
  const ui = defaultUiModeForOnboarding(status);
  const base = {
    path: "/",
    maxAge: DASHBOARD_PREF_COOKIE_MAX_AGE,
    sameSite: "lax" as const,
    httpOnly: false,
  };
  res.cookies.set(ONBOARDING_COOKIE_NAME, status, base);
  res.cookies.set(UI_MODE_COOKIE_NAME, ui, base);
}

/** GET: aktueller Onboarding-Status (fuer UI). */
export async function GET() {
  const jar = await cookies();
  const v = jar.get(ONBOARDING_COOKIE_NAME)?.value;
  return NextResponse.json({
    status: settledStatus(v),
  });
}

/** POST { status: "complete" | "skipped" } — setzt Onboarding- und UI-Modus-Cookies. */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }
  const status = (body as { status?: string }).status;
  if (status !== "complete" && status !== "skipped") {
    return NextResponse.json({ error: "invalid_status" }, { status: 400 });
  }
  const res = NextResponse.json({ ok: true, status });
  applyOnboardingCookies(res, status);
  return res;
}
