import type { NextResponse } from "next/server";

import { LOCALE_COOKIE_NAME, type Locale } from "./config";

const MAX_AGE_SEC = 60 * 60 * 24 * 400;

/** Gleiche Cookie-Policy wie POST /api/locale (Browser + optional BFF-Spiegel). */
export function applyLocaleCookie(res: NextResponse, locale: Locale): void {
  res.cookies.set(LOCALE_COOKIE_NAME, locale, {
    path: "/",
    maxAge: MAX_AGE_SEC,
    sameSite: "lax",
    httpOnly: false,
  });
}
