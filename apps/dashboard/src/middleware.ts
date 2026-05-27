import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { isLocale, LOCALE_COOKIE_NAME } from "@/lib/i18n/config";
import { CONSOLE_BASE, PORTAL_BASE } from "@/lib/console-paths";
import { getDashboardPersonaFromRequest } from "@/lib/portal-persona";

function pathnameIsStaticAsset(pathname: string): boolean {
  return /\.(ico|png|jpg|jpeg|gif|webp|svg|txt|xml|webmanifest)$/i.test(
    pathname,
  );
}

function isPublicPath(pathname: string): boolean {
  if (pathname === "/welcome") return true;
  if (pathname === "/login") return true;
  if (pathname.startsWith("/api/")) return true; // BFF-Routen verwalten Auth selbst
  if (pathname.startsWith("/_next")) return true;
  if (pathnameIsStaticAsset(pathname)) return true;
  return false;
}

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Statische Assets oder Public-Pfade durchlassen
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // 1. Locale-Prüfung: Falls keine Locale gesetzt ist, zu /welcome umleiten
  const rawLocale = request.cookies.get(LOCALE_COOKIE_NAME)?.value;
  if (!isLocale(rawLocale)) {
    const url = request.nextUrl.clone();
    url.pathname = "/welcome";
    url.searchParams.set("returnTo", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }

  // 2. Authentifizierung und Persona-Validierung
  const persona = await getDashboardPersonaFromRequest(request);

  // Root-Pfad: Je nach Rolle weiterleiten
  if (pathname === "/") {
    const url = request.nextUrl.clone();
    if (persona === "customer") {
      url.pathname = PORTAL_BASE;
    } else if (persona === "operator") {
      url.pathname = CONSOLE_BASE;
    } else {
      url.pathname = "/login";
    }
    url.search = "";
    return NextResponse.redirect(url);
  }

  // Keine gültige Session
  if (persona === "unknown") {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("returnTo", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }

  // 3. Zonen-Isolation (Least Privilege)
  // a) /portal/* (Kunden-Zone)
  if (pathname.startsWith("/portal")) {
    if (persona !== "customer" && persona !== "operator") {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      url.searchParams.set("returnTo", `${pathname}${search}`);
      return NextResponse.redirect(url);
    }
  }

  // b) /console/* (Operator-Zone)
  if (pathname.startsWith("/console")) {
    if (persona !== "operator") {
      const url = request.nextUrl.clone();
      if (persona === "customer") {
        url.pathname = PORTAL_BASE;
        url.search = "";
      } else {
        url.pathname = "/login";
        url.searchParams.set("returnTo", `${pathname}${search}`);
      }
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
