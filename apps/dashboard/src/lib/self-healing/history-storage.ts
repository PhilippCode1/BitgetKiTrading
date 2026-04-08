import type { SelfHealingHistoryEntry } from "@/lib/self-healing/schema";

export const SELF_HEALING_HISTORY_KEY = "self_healing_history_v1";
export const SELF_HEALING_HISTORY_MAX = 40;

export function loadSelfHealingHistory(): SelfHealingHistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(SELF_HEALING_HISTORY_KEY);
    if (!raw) return [];
    const p = JSON.parse(raw) as unknown;
    if (!Array.isArray(p)) return [];
    return p.filter(
      (x) =>
        x &&
        typeof x === "object" &&
        typeof (x as SelfHealingHistoryEntry).ts_ms === "number",
    ) as SelfHealingHistoryEntry[];
  } catch {
    return [];
  }
}

export function saveSelfHealingHistory(entries: SelfHealingHistoryEntry[]) {
  try {
    sessionStorage.setItem(
      SELF_HEALING_HISTORY_KEY,
      JSON.stringify(entries.slice(0, SELF_HEALING_HISTORY_MAX)),
    );
  } catch {
    /* private mode */
  }
}
