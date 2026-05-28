import { Header } from "@/components/layout/Header";
import { SafetyCommandActions } from "@/components/safety/SafetyCommandActions";
import {
  fetchLiveBrokerKillSwitchActive,
  fetchLiveBrokerRuntime,
  fetchSystemHealthBestEffort,
} from "@/lib/api";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { LiveBrokerRuntimeItem } from "@/lib/types";

function statusLabel(
  value: unknown,
  okValue: string,
  unknownLabel: string,
): string {
  if (typeof value !== "string" || !value.trim()) return unknownLabel;
  return value === okValue ? "OK" : value;
}

function boolLabel(
  value: boolean | null | undefined,
  activeLabel: string,
  inactiveLabel: string,
  unknownLabel: string,
): string {
  if (value === true) return activeLabel;
  if (value === false) return inactiveLabel;
  return unknownLabel;
}

function buildNoGoReasons(
  runtime: LiveBrokerRuntimeItem | null,
  hasKillSwitch: boolean,
  healthMissing: boolean,
  t: (key: string) => string,
): string[] {
  const reasons: string[] = [];
  const reconcileStatus = String(runtime?.status ?? "").toLowerCase();
  if (!runtime) reasons.push(t("console.safetyCenterPage.reasonRuntime"));
  if (hasKillSwitch) reasons.push(t("console.safetyCenterPage.reasonKillSwitch"));
  if (runtime?.safety_latch_active === true)
    reasons.push(t("console.safetyCenterPage.reasonSafetyLatch"));
  if (
    !reconcileStatus ||
    reconcileStatus === "unknown" ||
    reconcileStatus === "stale" ||
    reconcileStatus === "fail"
  ) {
    reasons.push(t("console.safetyCenterPage.reasonReconcile"));
  }
  if (runtime?.upstream_ok !== true)
    reasons.push(t("console.safetyCenterPage.reasonExchangeTruth"));
  if (healthMissing) reasons.push(t("console.safetyCenterPage.reasonHealth"));
  return reasons;
}

export const dynamic = "force-dynamic";

export default async function SafetyCenterPage() {
  const t = await getServerTranslator();
  const [runtimeRes, killRes, healthRes] = await Promise.allSettled([
    fetchLiveBrokerRuntime(),
    fetchLiveBrokerKillSwitchActive(),
    fetchSystemHealthBestEffort(),
  ]);

  const runtime =
    runtimeRes.status === "fulfilled" ? runtimeRes.value.item : null;
  const killActiveCount =
    killRes.status === "fulfilled" ? (killRes.value.items ?? []).length : 0;
  const health =
    healthRes.status === "fulfilled" ? healthRes.value.health : null;

  const mode = runtime?.execution_mode ?? "unknown";
  const liveLane =
    runtime?.operator_live_submission?.lane ?? "live_lane_unknown";
  const reconcileStatus = runtime?.status ?? "unknown";
  const exchangeTruth =
    runtime?.upstream_ok === true
      ? t("console.safetyCenterPage.exchangePresent")
      : runtime?.upstream_ok === false
        ? t("console.safetyCenterPage.exchangeMissing")
        : t("console.safetyCenterPage.exchangeUnchecked");
  const bitgetPrivate = runtime?.bitget_private_status;
  const readiness =
    bitgetPrivate?.public_api_ok === true &&
    bitgetPrivate?.private_api_configured === true
      ? t("console.safetyCenterPage.readinessOk")
      : t("console.safetyCenterPage.unknown");

  const assetCounts = runtime?.instrument_catalog?.counts ?? {};
  const chartFaehig = Number(assetCounts.catalog_total ?? 0);
  const shadowFaehig = Number(assetCounts.shadow_allowed ?? 0);
  const liveFaehig = Number(assetCounts.live_allowed ?? 0);
  const blockiert = Number(assetCounts.blocked ?? 0);

  const noGoReasons = buildNoGoReasons(runtime, killActiveCount > 0, !health, t);
  const liveBlocked = noGoReasons.length > 0;
  const unknown = t("console.safetyCenterPage.unknown");

  return (
    <>
      <Header
        title={t("console.safetyCenterPage.title")}
        subtitle={t("console.safetyCenterPage.subtitle")}
      />

      <div className="panel">
        <h2>{t("console.safetyCenterPage.overallTitle")}</h2>
        <p>
          {t("console.safetyCenterPage.liveStatusLabel")}:{" "}
          <strong>
            {liveBlocked
              ? t("console.safetyCenterPage.liveStatusBlocked")
              : t("console.safetyCenterPage.liveStatusPrepared")}
          </strong>
        </p>
        <p className="muted small">
          {t("console.safetyCenterPage.failClosedNote")}
        </p>
      </div>

      <div className="panel">
        <h2>{t("console.safetyCenterPage.cardsTitle")}</h2>
        <div className="table-wrap">
          <table className="data-table data-table--dense">
            <thead>
              <tr>
                <th>{t("console.safetyCenterPage.colCard")}</th>
                <th>{t("console.safetyCenterPage.colStatus")}</th>
                <th>{t("console.safetyCenterPage.colHint")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{t("console.safetyCenterPage.rowSystemMode")}</td>
                <td>{mode}</td>
                <td>{t("console.safetyCenterPage.hintSystemMode")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowLiveTradingStatus")}</td>
                <td>{liveLane}</td>
                <td>{t("console.safetyCenterPage.hintLiveTradingStatus")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowKillSwitch")}</td>
                <td>
                  {killActiveCount > 0
                    ? t("console.safetyCenterPage.active")
                    : t("console.safetyCenterPage.inactive")}
                </td>
                <td>
                  {t("console.safetyCenterPage.killSwitchActiveEvents", {
                    count: String(killActiveCount),
                  })}
                </td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowSafetyLatch")}</td>
                <td>
                  {boolLabel(
                    runtime?.safety_latch_active,
                    t("console.safetyCenterPage.activeYes"),
                    t("console.safetyCenterPage.inactiveNo"),
                    unknown,
                  )}
                </td>
                <td>{t("console.safetyCenterPage.hintSafetyLatch")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowReconcile")}</td>
                <td>{statusLabel(reconcileStatus, "ok", unknown)}</td>
                <td>{t("console.safetyCenterPage.hintReconcile")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowExchangeTruth")}</td>
                <td>{exchangeTruth}</td>
                <td>{t("console.safetyCenterPage.hintExchangeTruth")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowBitgetReadiness")}</td>
                <td>{readiness}</td>
                <td>{t("console.safetyCenterPage.hintBitgetReadiness")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowAssetApproval")}</td>
                <td>
                  {t("console.safetyCenterPage.assetApprovalStatus", {
                    chart: String(chartFaehig),
                    shadow: String(shadowFaehig),
                    live: String(liveFaehig),
                    blocked: String(blockiert),
                  })}
                </td>
                <td>{t("console.safetyCenterPage.hintAssetApproval")}</td>
              </tr>
              <tr>
                <td>{t("console.safetyCenterPage.rowEmergencyActions")}</td>
                <td>{t("console.safetyCenterPage.emergencyActionsStatus")}</td>
                <td>{t("console.safetyCenterPage.hintEmergencyActions")}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h2>{t("console.safetyCenterPage.noGoTitle")}</h2>
        {noGoReasons.length ? (
          <ul className="news-list">
            {noGoReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">
            {t("console.safetyCenterPage.noGoEmpty")}
          </p>
        )}
        <p className="muted small">
          {t("console.safetyCenterPage.noGoFooter")}
        </p>
      </div>

      <SafetyCommandActions />
    </>
  );
}
