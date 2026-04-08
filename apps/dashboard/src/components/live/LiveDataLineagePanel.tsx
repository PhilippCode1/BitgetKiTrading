"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LiveDataLineageSegment } from "@/lib/types";

type Props = {
  segments: LiveDataLineageSegment[] | undefined;
  onlineDriftEffective?: string | null;
  onlineDriftComputedAt?: string | null;
};

export function LiveDataLineagePanel({
  segments,
  onlineDriftEffective,
  onlineDriftComputedAt,
}: Props) {
  const { locale, t } = useI18n();
  const list = segments ?? [];
  if (!list.length) return null;
  const missing = list.filter((s) => !s.has_data).length;
  const withData = list.filter((s) => s.has_data).length;
  const en = locale === "en";

  return (
    <details className="panel live-lineage-details" open={missing > 0}>
      <summary>
        <strong>{t("live.lineage.title")}</strong>
        <span className="muted small">
          {" "}
          (
          {t("live.lineage.summary", {
            ok: withData,
            total: list.length,
          })}
          {onlineDriftEffective
            ? t("live.lineage.driftInline", { action: onlineDriftEffective })
            : ""}
          )
        </span>
      </summary>
      <p className="muted small live-lineage-lead">{t("live.lineage.lead")}</p>
      {onlineDriftComputedAt ? (
        <p className="muted small">
          {t("live.lineage.driftComputed", { at: onlineDriftComputedAt })}
        </p>
      ) : null}
      <ul className="news-list live-lineage-list">
        {list.map((s) => {
          const label = en ? s.label_en : s.label_de;
          const producer = en ? s.producer_en : s.producer_de;
          const why = en ? s.why_empty_en : s.why_empty_de;
          const next = en ? s.next_step_en : s.next_step_de;
          return (
            <li
              key={s.segment_id}
              className={s.has_data ? "" : "live-lineage-gap"}
            >
              <div>
                <strong>{label}</strong>{" "}
                <span
                  className={
                    s.has_data ? "live-lineage-ok" : "live-lineage-warn"
                  }
                >
                  {s.has_data
                    ? t("live.lineage.statusOk")
                    : t("live.lineage.statusGap")}
                </span>
              </div>
              <div className="muted small">
                {t("live.lineage.source")} {producer}
              </div>
              {!s.has_data && why ? <p className="small">{why}</p> : null}
              {!s.has_data && next ? (
                <p className="muted small">
                  <strong>{t("live.lineage.nextStep")}</strong> {next}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
