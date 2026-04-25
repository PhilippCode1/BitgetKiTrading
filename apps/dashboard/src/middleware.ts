import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import {
  isOnboardingSettled,
  ONBOARDING_COOKIE_NAME,
} from "@/lib/dashboard-prefs";
import { isLocale, LOCALE_COOKIE_NAME } from "@/lib/i18n/config";
import { hasAdminSessionFromDashboardEnv } from "@/lib/operator-jwt";
import { CONSOLE_BASE } from "@/lib/console-paths";
import { decideConsoleAccess } from "@/lib/middleware-console-guard";

const LEGACY_SCOPE_BLOCKED_PREFIXES: readonly string[] = [
  "/portal",
  "/console/account/billing",
  "/console/account/payments",
  "/console/admin/billing",
  "/console/admin/commerce-payments",
  "/console/admin/customers",
  "/console/admin/contracts",
];

function pathnameIsStaticAsset(pathname: string): boolean {
  return /\.(ico|png|jpg|jpeg|gif|webp|svg|txt|xml|webmanifest)$/i.test(
    pathname,
  );
}

function isLocaleBypassPath(pathname: string): boolean {
  if (pathname === "/welcome") return true;
  if (pathname === "/onboarding") return true;
  if (pathname.startsWith("/api/")) return true;
  if (pathname.startsWith("/_next")) return true;
  if (pathnameIsStaticAsset(pathname)) return true;
  return false;
}

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isLocaleBypassPath(pathname)) {
    return NextResponse.next();
  }

  if (LEGACY_SCOPE_BLOCKED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    const url = request.nextUrl.clone();
    url.pathname = "/console";
    url.search = "";
    return NextResponse.redirect(url);
  }

  const raw = request.cookies.get(LOCALE_COOKIE_NAME)?.value;
  if (isLocale(raw)) {
    const consoleDecision = await decideConsoleAccess(request, pathname);
    if (consoleDecision.action === "redirect") {
      const url = request.nextUrl.clone();
      url.pathname = consoleDecision.location;
      url.search = "";
      return NextResponse.redirect(url);
    }
    if (
      pathname.startsWith("/console") &&
      !isOnboardingSettled(request.cookies.get(ONBOARDING_COOKIE_NAME)?.value)
    ) {
      const url = request.nextUrl.clone();
      url.pathname = "/onboarding";
      url.searchParams.set("returnTo", `${pathname}${search}`);
      return NextResponse.redirect(url);
    }
    if (pathname.startsWith("/console/admin")) {
      const adminFeatureOff =
        (process.env.NEXT_PUBLIC_ENABLE_ADMIN ?? "true").trim().toLowerCase() ===
        "false";
      if (
        adminFeatureOff ||
        !(await hasAdminSessionFromDashboardEnv())
      ) {
        const url = request.nextUrl.clone();
        url.pathname = "/console";
        return NextResponse.redirect(url);
      }
    }
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = "/welcome";
  const returnTo =
    pathname === "/" ? CONSOLE_BASE : `${pathname}${search}`;
  if (returnTo && returnTo !== "/welcome") {
    url.searchParams.set("returnTo", returnTo);
  }
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
