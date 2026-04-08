import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { isLocale, LOCALE_COOKIE_NAME, type Locale } from "@/lib/i18n/config";
import { applyLocaleCookie } from "@/lib/i18n/set-locale-cookie";

export async function GET() {
  const jar = await cookies();
  const v = jar.get(LOCALE_COOKIE_NAME)?.value;
  return NextResponse.json({ locale: isLocale(v) ? v : null });
}

/**
 * Setzt die UI-Sprache (Cookie). Kataloge: src/messages/*.json — Fallback bei fehlenden Keys auf DEFAULT_LOCALE.
 */
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
  const loc = (body as { locale?: string }).locale;
  if (!isLocale(loc)) {
    return NextResponse.json({ error: "unsupported_locale" }, { status: 400 });
  }
  const locale = loc as Locale;
  const res = NextResponse.json({ ok: true, locale });
  applyLocaleCookie(res, locale);
  return res;
}
