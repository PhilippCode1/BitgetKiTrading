import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  DASHBOARD_PREF_COOKIE_MAX_AGE,
  isUiMode,
  type UiMode,
  UI_MODE_COOKIE_NAME,
} from "@/lib/dashboard-prefs";

export async function GET() {
  const jar = await cookies();
  const v = jar.get(UI_MODE_COOKIE_NAME)?.value;
  return NextResponse.json({ mode: isUiMode(v) ? v : null });
}

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
  const mode = (body as { mode?: string }).mode;
  if (!isUiMode(mode)) {
    return NextResponse.json({ error: "invalid_mode" }, { status: 400 });
  }
  const m = mode as UiMode;
  const res = NextResponse.json({ ok: true, mode: m });
  res.cookies.set(UI_MODE_COOKIE_NAME, m, {
    path: "/",
    maxAge: DASHBOARD_PREF_COOKIE_MAX_AGE,
    sameSite: "lax",
    httpOnly: false,
  });
  return res;
}
