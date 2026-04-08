import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

/**
 * Einheitlicher Teil-Ladezustand: mehrere Sektionen fehlgeschlagen, andere liefern noch Daten.
 * Ersetzt kopiertes panel+notice+Listen-Markup auf Paper, Live-Broker, Shadow-Live.
 */
export function ConsolePartialLoadNotice({
  t,
  titleKey,
  bodyKey,
  lines,
  diagnostic,
  showStateActions = true,
}: Readonly<{
  t: TranslateFn;
  titleKey: string;
  bodyKey: string;
  lines: readonly string[];
  diagnostic: boolean;
  showStateActions?: boolean;
}>) {
  if (lines.length === 0) return null;
  const uniqueLines = [...new Set(lines.map((s) => s.trim()).filter(Boolean))];
  const technical = uniqueLines.join("\n");
  return (
    <ConsoleFetchNotice
      variant="soft"
      title={t(titleKey)}
      body={t(bodyKey)}
      showStateActions={showStateActions}
      technical={technical}
      showTechnical={diagnostic}
      diagnosticSummaryLabel={t("ui.diagnostic.summary")}
      className="panel"
    >
      <ul className="news-list muted small">
        {uniqueLines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </ConsoleFetchNotice>
  );
}
