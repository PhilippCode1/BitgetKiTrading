/**
 * Zentrales, produktreifes Meldungsschema (Dashboard).
 * Trennt menschenlesbare Ebenen von technischer Diagnose; Actions sind bewusst kurz beschriftet.
 */

export type ProductMessageSeverity =
  | "info"
  | "hint"
  | "warning"
  | "critical"
  | "blocking";

/** Stabile Schlüssel für Deduplizierung gleicher Ursachen auf einer Fläche. */
export type ProductMessage = Readonly<{
  id: string;
  dedupeKey: string;
  severity: ProductMessageSeverity;
  /** Kurz, z. B. „Kern-API“, „Diese Ansicht“, „Anmeldung“. */
  areaLabel: string;
  /** Zeile 1 — was ist sichtbar kaputt / eingeschränkt. */
  headline: string;
  /** 1–2 Sätze: konkret was fehlt oder gebrochen ist. */
  summary: string;
  /** Warum das für Nutzung oder Entscheidungen problematisch ist. */
  impact: string;
  /** Eine Zeile Dringlichkeit (kein Alarmismus). */
  urgency: string;
  /** Was die Plattform selbst tut (Retries, Warteschlangen, Degradation). */
  appDoing: string;
  /** Was der Nutzer sinnvoll tun kann; leer = nichts Nötiges. */
  userAction: string;
  /** Roh-/JSON/HTTP — nur in technischer Klappe. */
  technicalDetail: string;
}>;

const SEVERITY_RANK: Record<ProductMessageSeverity, number> = {
  info: 0,
  hint: 1,
  warning: 2,
  critical: 3,
  blocking: 4,
};

export function severityRank(s: ProductMessageSeverity): number {
  return SEVERITY_RANK[s] ?? 0;
}

/**
 * Pro dedupeKey eine Meldung behalten — die höchste Dringlichkeit gewinnt.
 * Reihenfolge innerhalb gleicher Stufe: erste gewinnt (stabil).
 */
export function dedupeProductMessages(
  messages: readonly ProductMessage[],
): ProductMessage[] {
  const best = new Map<string, ProductMessage>();
  for (const m of messages) {
    const prev = best.get(m.dedupeKey);
    if (!prev || severityRank(m.severity) > severityRank(prev.severity)) {
      best.set(m.dedupeKey, m);
    }
  }
  return [...best.values()].sort(
    (a, b) => severityRank(b.severity) - severityRank(a.severity),
  );
}
