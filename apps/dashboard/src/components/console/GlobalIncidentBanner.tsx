import { Suspense } from "react";

import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";
import { IssueCenterQuickActions } from "@/components/console/IssueCenterQuickActions";
import type {
  OpsModuleId,
  SecondaryIncidentGroup,
  TransportCascade,
} from "@/lib/upstream-incidents";
import { buildProductMessageFromFetchErrorMessage } from "@/lib/product-messages";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

type Props = Readonly<{
  cascade: TransportCascade;
  secondary: SecondaryIncidentGroup[];
  diagnostic: boolean;
  t: TranslateFn;
}>;

function moduleLabels(ids: readonly OpsModuleId[], t: TranslateFn): string {
  return ids
    .map((id) => t(`ui.incident.modules.${id}`))
    .filter(Boolean)
    .join(", ");
}

type SecondaryProps = Readonly<{
  secondary: SecondaryIncidentGroup[];
  diagnostic: boolean;
  t: TranslateFn;
}>;

/** Abweichende Fehlergruppen ohne Kaskadenkopf (z. B. wenn Layout-Bootstrap schon die Hauptursache zeigt). */
export function SecondaryIncidentsStrip({
  secondary,
  diagnostic,
  t,
}: SecondaryProps) {
  if (secondary.length === 0) return null;
  return (
    <div
      className="global-incident global-incident--secondary"
      role="region"
      aria-label={t("ui.incident.secondaryTitle")}
    >
      <p className="global-incident__secondary-title small">
        {t("ui.incident.secondaryTitle")}
      </p>
      <ul className="global-incident__secondary-list">
        {secondary.map((g, i) => {
          const secPm = buildProductMessageFromFetchErrorMessage(
            g.sampleRaw,
            t,
          );
          const mods = moduleLabels(g.modules, t);
          return (
            <li key={`${g.kind}-${i}`}>
              <span className="global-incident__secondary-kind">
                {secPm.headline}
              </span>
              <span className="muted small"> — {mods}</span>
              {diagnostic ? (
                <pre
                  className="console-fetch-notice__pre small"
                  style={{ marginTop: 6 }}
                >
                  {g.sampleRaw}
                </pre>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Zentrale Meldung bei gemeinsamer Gateway-/Transport-Kaskade statt N identischer Panel-Fehler.
 */
export function GlobalIncidentBanner({
  cascade,
  secondary,
  diagnostic,
  t,
}: Props) {
  const pm = buildProductMessageFromFetchErrorMessage(cascade.sampleRaw, t);
  const affected = moduleLabels(cascade.affectedModules, t);
  const cascadeClass =
    cascade.severity === "blocker"
      ? "global-incident global-incident--cascade global-incident--blocker"
      : "global-incident global-incident--cascade";

  return (
    <div
      className="global-incident-stack"
      role="region"
      aria-label={t("ui.incident.regionLabel")}
    >
      <div className={cascadeClass}>
        <p className="global-incident__priority small">
          {cascade.severity === "blocker"
            ? t("ui.incident.priorityBlocker")
            : t("ui.incident.priorityDegraded")}
        </p>
        <ConsoleFetchNotice
          variant="soft"
          title={t("ui.incident.cascadeTitle")}
          body={t("ui.incident.cascadeBody", { count: cascade.count })}
          refreshHint={t("ui.refreshHint")}
          technical={`${pm.headline}\n${pm.summary}\n${cascade.sampleRaw}`}
          showTechnical={diagnostic}
          diagnosticSummaryLabel={t("ui.diagnostic.summary")}
        />
        <p className="global-incident__kind muted small">{pm.summary}</p>
        <p className="global-incident__modules muted small">
          <strong>{t("ui.incident.affectedLabel")}</strong> {affected}
        </p>
        <p className="global-incident__hint muted small">
          {t("ui.incident.cascadeHint")}
        </p>
        <Suspense fallback={null}>
          <IssueCenterQuickActions />
        </Suspense>
      </div>
      <SecondaryIncidentsStrip
        secondary={secondary}
        diagnostic={diagnostic}
        t={t}
      />
    </div>
  );
}
