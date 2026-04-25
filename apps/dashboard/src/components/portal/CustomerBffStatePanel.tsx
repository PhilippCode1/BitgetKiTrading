import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { CustomerPortalSummary } from "@/lib/customer-portal-summary";

type Props = Readonly<{
  summary: CustomerPortalSummary;
}>;

function dataStateKey(s: CustomerPortalSummary["dataState"]): string {
  switch (s) {
    case "ok":
      return "customerPortal.bffState.ok";
    case "degraded":
      return "customerPortal.bffState.degraded";
    case "not_configured":
      return "customerPortal.bffState.notConfigured";
    case "backend_unavailable":
      return "customerPortal.bffState.backendUnavailable";
    default:
      return "customerPortal.bffState.unknown";
  }
}

/**
 * Kompakte Anzeige des BFF-Status; keine vollstaendigen API-Rumpfe (nur Status + Kurzangaben).
 */
export async function CustomerBffStatePanel({ summary }: Props) {
  const t = await getServerTranslator();
  return (
    <div
      className="panel muted"
      data-e2e="customer-bff-state"
      style={{ fontSize: "0.95rem", lineHeight: 1.55 }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>{t("customerPortal.bffState.title")}</h2>
      <p>
        <strong>{t("customerPortal.bffState.aggregate")}</strong>{" "}
        {t(dataStateKey(summary.dataState))}
      </p>
      {summary.notConfiguredReason === "api_gateway_url_missing" && (
        <p>
          <strong>{t("customerPortal.bffState.reason")}</strong>{" "}
          {t("customerPortal.bffState.reasons.apiGatewayUrlMissing")}
        </p>
      )}
      {summary.notConfiguredReason === "gateway_bff_auth_missing" && (
        <p>
          <strong>{t("customerPortal.bffState.reason")}</strong>{" "}
          {t("customerPortal.bffState.reasons.gatewayBffAuthMissing")}
        </p>
      )}
      {summary.commerceCustomerMe && (
        <p>
          <strong>{t("customerPortal.bffState.commerceMe")}</strong>{" "}
          {summary.commerceCustomerMe.httpStatus}{" "}
          {summary.commerceCustomerMe.body
            ? t("customerPortal.bffState.parsed")
            : t("customerPortal.bffState.unparsedOrEmpty")}
        </p>
      )}
      {summary.errorHint && (
        <p data-e2e="customer-bff-hint" className="small" style={{ opacity: 0.9 }}>
          {t("customerPortal.bffState.hintPrefix")} {summary.errorHint}
        </p>
      )}
      <p className="small" style={{ marginTop: 12, opacity: 0.85 }}>
        {t("customerPortal.bffState.tradingStub")}
      </p>
    </div>
  );
}
