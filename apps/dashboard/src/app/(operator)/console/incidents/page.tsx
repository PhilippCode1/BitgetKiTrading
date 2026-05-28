import type { CSSProperties } from "react";

import { Header } from "@/components/layout/Header";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import {
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerRuntime,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { getRequestLocale } from "@/lib/i18n/server";
import { localizeOperatorAlert } from "@/lib/operator-alert-locale";
import { buildOperatorAlertsFromConsoleSnapshot } from "@/lib/operator-alerts-view-model";
import type {
  OperatorAlertView,
  OperatorSeverity,
} from "@/lib/operator-alerts-view-model";

export const dynamic = "force-dynamic";

function severityFrame(sev: OperatorSeverity): CSSProperties {
  if (sev === "P0") {
    return {
      borderLeft: "4px solid var(--danger, #e07070)",
      background: "var(--danger-muted, rgba(224, 112, 112, 0.12))",
    };
  }
  if (sev === "P1") {
    return {
      borderLeft: "4px solid var(--warning, #d4a017)",
      background: "rgba(212, 160, 23, 0.08)",
    };
  }
  if (sev === "P2") {
    return { borderLeft: "4px solid var(--fg-muted, #888)" };
  }
  return { borderLeft: "4px solid var(--border, #444)" };
}

type AlertLabels = Readonly<{
  liveBlocked: string;
  yes: string;
  no: string;
  component: string;
  assets: string;
  recommended: string;
  nextStep: string;
  time: string;
  correlation: string;
  techDetails: string;
}>;

function AlertCard({
  alert,
  labels,
  locale,
}: {
  alert: OperatorAlertView;
  labels: AlertLabels;
  locale: "de" | "en";
}) {
  const text = localizeOperatorAlert(alert, locale);
  return (
    <article
      className="panel operator-alert-card"
      style={severityFrame(alert.severity)}
    >
      <header className="operator-alert-card__head">
        <span
          className="operator-alert-card__sev"
          data-severity={alert.severity}
        >
          {alert.severity}
        </span>
        <h3 className="operator-alert-card__title">{text.title}</h3>
      </header>
      <p>{text.description}</p>
      <dl className="operator-alert-card__dl">
        <div>
          <dt>{labels.liveBlocked}</dt>
          <dd>{alert.live_blockiert ? labels.yes : labels.no}</dd>
        </div>
        <div>
          <dt>{labels.component}</dt>
          <dd>{alert.betroffene_komponente}</dd>
        </div>
        <div>
          <dt>{labels.assets}</dt>
          <dd>
            {alert.betroffene_assets.length
              ? alert.betroffene_assets.join(", ")
              : "—"}
          </dd>
        </div>
        <div>
          <dt>{labels.recommended}</dt>
          <dd>{text.recommended}</dd>
        </div>
        <div>
          <dt>{labels.nextStep}</dt>
          <dd>{text.nextStep}</dd>
        </div>
        <div>
          <dt>{labels.time}</dt>
          <dd>{alert.zeitpunkt}</dd>
        </div>
        <div>
          <dt>{labels.correlation}</dt>
          <dd className="muted small">{alert.korrelation_id}</dd>
        </div>
      </dl>
      {alert.technische_details_redacted ? (
        <p className="muted small">
          <strong>{labels.techDetails}:</strong>{" "}
          {alert.technische_details_redacted}
        </p>
      ) : null}
    </article>
  );
}

export default async function IncidentsPage() {
  const locale = await getRequestLocale();
  const t = await getServerTranslator();
  const labels: AlertLabels = {
    liveBlocked: t("console.incidentsPage.liveBlocked"),
    yes: t("console.incidentsPage.yes"),
    no: t("console.incidentsPage.no"),
    component: t("console.incidentsPage.component"),
    assets: t("console.incidentsPage.assets"),
    recommended: t("console.incidentsPage.recommended"),
    nextStep: t("console.incidentsPage.nextStep"),
    time: t("console.incidentsPage.time"),
    correlation: t("console.incidentsPage.correlation"),
    techDetails: t("console.incidentsPage.techDetails"),
  };
  const [runtimeRes, killRes, healthRes] = await Promise.allSettled([
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchSystemHealthBestEffort(),
  ]);

  const runtime =
    runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const killCount =
    killRes.status === "fulfilled" ? (killRes.value.items ?? []).length : 0;
  const health =
    healthRes.status === "fulfilled" ? healthRes.value.health : null;

  const activeAlerts = buildOperatorAlertsFromConsoleSnapshot({
    health,
    runtime,
    killSwitchActiveCount: killCount,
  });

  const aktivListe = activeAlerts.filter((a) => a.aktiv);
  const historischListe = activeAlerts.filter((a) => !a.aktiv);

  return (
    <>
      <Header
        title={t("console.incidentsPage.title")}
        subtitle={t("console.incidentsPage.subtitle")}
      />

      <div className="panel">
        <h2>{t("console.incidentsPage.escalationTitle")}</h2>
        <ul className="muted small">
          <li>{t("console.incidentsPage.escalationP0")}</li>
          <li>{t("console.incidentsPage.escalationP1")}</li>
          <li>{t("console.incidentsPage.escalationP2")}</li>
          <li>{t("console.incidentsPage.escalationP3")}</li>
        </ul>
        <p className="muted small">
          {t("console.incidentsPage.escalationFootnote")}
        </p>
      </div>

      <div className="panel">
        <h2>{t("console.incidentsPage.activeTitle")}</h2>
        {aktivListe.length === 0 ? (
          <p className="muted">{t("console.incidentsPage.activeEmpty")}</p>
        ) : (
          <div
            className="stack"
            style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
          >
            {aktivListe.map((a) => (
              <AlertCard
                key={a.korrelation_id}
                alert={a}
                labels={labels}
                locale={locale}
              />
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>{t("console.incidentsPage.historyTitle")}</h2>
        {historischListe.length === 0 ? (
          <p className="muted">{t("console.incidentsPage.historyEmpty")}</p>
        ) : (
          <div
            className="stack"
            style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
          >
            {historischListe.map((a) => (
              <AlertCard
                key={a.korrelation_id}
                alert={a}
                labels={labels}
                locale={locale}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
