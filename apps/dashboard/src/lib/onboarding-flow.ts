import { CONSOLE_BASE } from "@/lib/console-paths";

/**
 * Ziel nach Abschluss oder Überspringen der ersten Schritte: Konsole-Start mit Kacheln
 * (Chart, KI, Paper) — nicht direkt ins Operator-Cockpit.
 */
export const ONBOARDING_DEFAULT_RETURN = CONSOLE_BASE;

export function onboardingUrlWithReturn(returnTo: string): string {
  const r = returnTo.trim().startsWith("/")
    ? returnTo.trim()
    : ONBOARDING_DEFAULT_RETURN;
  return `/onboarding?returnTo=${encodeURIComponent(r)}`;
}

/** Geführter Einstieg: Sprache wählen, dann Onboarding, dann `returnTo` (z. B. Konsole-Start). */
export function guidedWelcomeUrl(
  returnTo: string = ONBOARDING_DEFAULT_RETURN,
): string {
  return `/welcome?returnTo=${encodeURIComponent(onboardingUrlWithReturn(returnTo))}`;
}

/** Link „Erste Schritte“ in der Navigation: immer mit sinnvollem Zurück nach Abschluss. */
export const ONBOARDING_NAV_HREF = onboardingUrlWithReturn(
  ONBOARDING_DEFAULT_RETURN,
);
