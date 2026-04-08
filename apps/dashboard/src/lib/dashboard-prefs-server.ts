import { cookies } from "next/headers";

import { isUiMode, type UiMode, UI_MODE_COOKIE_NAME } from "./dashboard-prefs";

export async function getRequestUiMode(): Promise<UiMode> {
  const jar = await cookies();
  const raw = jar.get(UI_MODE_COOKIE_NAME)?.value;
  /** Ohne Cookie: einfache Ansicht (Endkunde). Pro ist eine bewusste Wahl. */
  return isUiMode(raw) ? raw : "simple";
}
