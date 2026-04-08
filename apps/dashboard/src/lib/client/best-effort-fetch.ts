/**
 * POST /api/dashboard/preferences/locale — Nebenpfad nach erfolgreichem /api/locale.
 * Fehler werden nicht verschluckt: console.warn mit Praefix `[dashboard]` (ops-greifbar).
 */
export async function mirrorLocalePreferenceToServer(
  locale: string,
): Promise<void> {
  try {
    const res = await fetch("/api/dashboard/preferences/locale", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
    if (!res.ok) {
      console.warn(
        `[dashboard] preferences/locale mirror: HTTP ${res.status} (Locale/Cookie ist trotzdem gesetzt)`,
      );
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(
      `[dashboard] preferences/locale mirror: ${msg} (Locale/Cookie ist trotzdem gesetzt)`,
    );
  }
}
