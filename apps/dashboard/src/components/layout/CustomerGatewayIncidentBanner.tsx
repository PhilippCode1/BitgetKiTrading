"use client";

import { useCallback, useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import {
  DASHBOARD_GATEWAY_CLIENT_FAILURE,
  type GatewayClientFailureDetail,
} from "@/lib/dashboard-client-gateway-events";
import { isValidFetchErrorKind } from "@/lib/user-facing-fetch-error";

const BG = "dashboard-bff-background-revalidate-failed";

/**
 * Zeigt oberhalb des Kunden-Portals eine sichtbare Betriebszeile, wenn
 * BFF/ Gateway-Aufrufe im Browser fehlschlagen (keine weisse Shell ohne Hinweis).
 */
export function CustomerGatewayIncidentBanner() {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  const [line, setLine] = useState("");

  const onGatewayFailure = useCallback(
    (ev: Event) => {
      const ce = ev as CustomEvent<GatewayClientFailureDetail | undefined>;
      const d = ce.detail;
      if (!d?.kind) {
        setLine(t("ui.incident.customerShellBannerDefault"));
        setVisible(true);
        return;
      }
      const k = d.kind;
      if (isValidFetchErrorKind(k)) {
        setLine(
          `${t(`ui.fetchError.${k}.title`)} — ${t(`ui.fetchError.${k}.body`)}`,
        );
      } else {
        setLine(t("ui.incident.customerShellBannerDefault"));
      }
      setVisible(true);
    },
    [t],
  );

  const onBackgroundFail = useCallback(
    (ev: Event) => {
      const ce = ev as CustomEvent<{ bffPath?: string } | undefined>;
      if (ce.detail?.bffPath) {
        setLine(
          `${t("ui.backgroundRefresh.failedTitle")} — ${t("ui.backgroundRefresh.failedBody")}`,
        );
        setVisible(true);
      }
    },
    [t],
  );

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    window.addEventListener(DASHBOARD_GATEWAY_CLIENT_FAILURE, onGatewayFailure);
    window.addEventListener(BG, onBackgroundFail);
    return () => {
      window.removeEventListener(
        DASHBOARD_GATEWAY_CLIENT_FAILURE,
        onGatewayFailure,
      );
      window.removeEventListener(BG, onBackgroundFail);
    };
  }, [onBackgroundFail, onGatewayFailure]);

  if (!visible) return null;

  return (
    <div
      className="customer-gateway-banner global-incident"
      role="status"
      aria-live="polite"
    >
      <p className="customer-gateway-banner__text small">{line}</p>
      <div className="customer-gateway-banner__actions">
        <a
          className="muted small mono-small"
          href="/api/dashboard/edge-status"
          target="_blank"
          rel="noreferrer"
        >
          {t("productMessage.actions.edgeDiagnostics")}
        </a>
        <button
          type="button"
          className="public-btn ghost"
          onClick={() => {
            setVisible(false);
            setLine("");
          }}
        >
          {t("ui.dismiss")}
        </button>
      </div>
    </div>
  );
}
