import type { TranslateFn } from "@/components/i18n/I18nProvider";
import type { LiveBrokerOperatorLiveSubmission } from "@/lib/types";

function stripClassForLane(
  lane: LiveBrokerOperatorLiveSubmission["lane"],
): string {
  if (lane === "live_lane_ready")
    return "operator-situation-strip operator-strip-live";
  if (
    lane === "live_lane_blocked_safety" ||
    lane === "live_lane_blocked_upstream" ||
    lane === "live_lane_degraded_reconcile"
  ) {
    return "operator-situation-strip operator-strip-critical";
  }
  return "operator-situation-strip operator-strip-warn";
}

/**
 * Prominente Live-/Safety-Zusammenfassung fuer Operatoren (kein stilles „nichts passiert“).
 */
export function LiveSubmissionOperatorStrip({
  summary,
  t,
}: Readonly<{
  summary: LiveBrokerOperatorLiveSubmission | null | undefined;
  t: TranslateFn;
}>) {
  if (!summary) return null;

  const titleKey = `pages.broker.liveLane.${summary.lane}` as const;
  const title = t(titleKey);

  return (
    <section
      className={stripClassForLane(summary.lane)}
      aria-label={t("pages.broker.liveSubmissionStripLabel")}
    >
      <div className="operator-strip-k">
        {t("pages.broker.liveSubmissionTitle")}
      </div>
      <p
        className="operator-strip-v"
        style={{ margin: "6px 0 4px", fontWeight: 600 }}
      >
        {title}
      </p>
      {summary.reasons_de.length > 0 ? (
        <ul className="news-list" style={{ marginTop: 8, marginBottom: 0 }}>
          {summary.reasons_de.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      ) : summary.lane === "live_lane_ready" ? (
        <p className="muted small" role="status" style={{ marginTop: 6 }}>
          {t("pages.broker.liveLaneReadyNoExtra")}
        </p>
      ) : null}
      <p className="muted small" style={{ marginTop: 10, marginBottom: 0 }}>
        {t("pages.broker.liveSubmissionMeta", {
          ks: summary.safety_kill_switch_count,
          latch: summary.safety_latch_active
            ? t("pages.broker.liveSubmissionLatchOn")
            : t("pages.broker.liveSubmissionLatchOff"),
        })}
      </p>
    </section>
  );
}
