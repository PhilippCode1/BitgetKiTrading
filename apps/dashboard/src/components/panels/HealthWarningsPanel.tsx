import type { HealthWarningDisplayItem } from "@/lib/types";

type Props = Readonly<{
  items: HealthWarningDisplayItem[];
  className?: string;
  heading?: string;
  /** Kurzes summary-Label fuer das einklappbare JSON (KI / Automation). */
  machineBlockToggleLabel?: string;
  /** Zeile unterhalb der Nutzer-Nachricht: betroffene Dienste. */
  relatedServicesPrefix?: string;
}>;

export function HealthWarningsPanel({
  items,
  className = "warn-banner",
  /** Neutral fallback if caller omits i18n (Health-Seite übergibt immer übersetzte Strings). */
  heading = "Data quality notes",
  machineBlockToggleLabel = "Technical details (JSON) — collapsed by default",
  relatedServicesPrefix = "Related services:",
}: Props) {
  if (!items.length) return null;
  return (
    <div className={className} role="status">
      <strong>{heading}</strong>
      <ul className="news-list health-warnings-list">
        {items.map((w, idx) => (
          <li key={`${w.code}-${idx}`} className="health-warning-item">
            <div className="health-warning-title">{w.title}</div>
            <p className="health-warning-msg">{w.message}</p>
            <p className="muted small">{w.next_step}</p>
            <p className="muted small">
              {relatedServicesPrefix} {w.related_services}
            </p>
            {w.machine ? (
              <details
                className="health-machine-block"
                style={{ marginTop: "0.75rem" }}
              >
                <summary className="muted small" style={{ cursor: "pointer" }}>
                  {machineBlockToggleLabel}
                </summary>
                <p className="muted small" style={{ marginTop: 8 }}>
                  <strong className="health-machine-severity">
                    {w.machine.severity}
                  </strong>{" "}
                  <span className="mono-small">{w.machine.problem_id}</span>
                </p>
                <p className="small" style={{ marginTop: 6 }}>
                  {w.machine.summary_en}
                </p>
                <pre
                  className="health-machine-json mono-small"
                  style={{ marginTop: 8, overflow: "auto" }}
                >
                  {JSON.stringify(w.machine, null, 2)}
                </pre>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
