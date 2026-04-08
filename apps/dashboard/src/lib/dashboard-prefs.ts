/** Browser-Cookies fuer gefuehrtes Onboarding und Ansichtsmodus (kein next/headers hier). */

export const ONBOARDING_COOKIE_NAME = "bitget_onboarding_status";
export type OnboardingStatus = "complete" | "skipped";

export const UI_MODE_COOKIE_NAME = "bitget_dashboard_ui_mode";
export type UiMode = "simple" | "pro";

export const DASHBOARD_PREF_COOKIE_MAX_AGE = 60 * 60 * 24 * 400;

export function isOnboardingSettled(value: string | null | undefined): boolean {
  return value === "complete" || value === "skipped";
}

export function isUiMode(value: string | null | undefined): value is UiMode {
  return value === "simple" || value === "pro";
}

export function defaultUiModeForOnboarding(_status: OnboardingStatus): UiMode {
  /** Nach Onboarding wie bei Erstbesuch: einfache Navigation; Pro ueber Schalter. */
  return "simple";
}
