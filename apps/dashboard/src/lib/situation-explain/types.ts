/**
 * Einheitliche Erklärstruktur für Fehler, Warnungen und Degradation —
 * deterministisch aus Fakten + optional LLM-Vertiefung (Operator Explain).
 */

export type SituationExplainSections = Readonly<{
  /** 1 — Alltagssprache, ohne Technik-Jargon wo möglich */
  problemPlain: string;
  /** 2 — kurze technische Einordnung (kann „unsicher“ sagen) */
  technicalCause: string;
  /** 3 — Relevanz für Nutzung / Entscheidungen */
  whyItMatters: string;
  /** 4 — betroffene Bereiche (Komponenten, Flächen) */
  affectedAreas: string;
  /** 5 — was die Plattform / das Dashboard bereits versucht hat */
  appAlreadyTried: string;
  /** 6 — empfohlene nächste Schritte */
  nextRecommended: string;
  /** 7 — Selbstheilung vs. manueller Eingriff */
  selfHealVsManual: string;
  /** Wenn true: mindestens ein Feld ist bewusst vage */
  hasUncertainty: boolean;
}>;
