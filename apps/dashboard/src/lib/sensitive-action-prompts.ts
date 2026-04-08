/**
 * Zentrale Texte für sensible UI-Aktionen (testbar, einheitlich).
 * Serverseitige Autorisierung bleibt maßgeblich; dies ist nur Client-Bestätigung.
 */

export function adminRulesSaveConfirmMessage(): string {
  return (
    "Regelset wirklich speichern? Das wirkt auf Gateway/Execution-Policies.\n\n" +
    "Bestätigen nur mit gültiger Rolle und nach Review des JSON."
  );
}

export function strategyLifecycleConfirmMessage(newStatus: string): string {
  const s = newStatus.trim().toLowerCase();
  const by: Record<string, string> = {
    promoted:
      "Strategie auf PROMOTED setzen? Wirkt auf Live-/Registry-Freigabe — nur nach Gates und Review.",
    candidate:
      "Strategie auf CANDIDATE setzen? Experimenteller Pfad — Auswirkungen auf Zuordnung prüfen.",
    shadow:
      "Strategie auf SHADOW? Shadow-Pfad nur — Live bleibt geschützt falls Gates greifen.",
    retired:
      "Strategie RETIRED? Deaktiviert Nutzung in Produktion — nur bewusst nach Ablösung.",
  };
  return (
    by[s] ??
    `Strategie-Status wirklich auf "${newStatus}" setzen? Server prüft Rollen/Rechte zusätzlich.`
  );
}
