export function formatTsMs(ms: number | null | undefined): string {
  if (ms == null || ms === 0) return "—";
  return new Date(ms).toLocaleString("de-DE");
}

/** ISO-8601 aus API (z. B. Integrationsmatrix). */
export function formatIsoTs(iso: string | null | undefined): string {
  if (!iso?.trim()) return "—";
  const d = Date.parse(iso);
  if (Number.isNaN(d)) return iso;
  return new Date(d).toLocaleString("de-DE");
}

export function formatNum(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPct01(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)} %`;
}

/** DB-Feld typischerweise als Anteil (0.01 = 1 %); Werte >1 als bereits Prozentpunkte interpretieren. */
export function formatDistancePctField(
  n: number | null | undefined,
  digits = 3,
): string {
  if (n == null || Number.isNaN(n)) return "—";
  const pct = n > 1 && n <= 100 ? n : n * 100;
  return `${formatNum(pct, digits)} %`;
}
