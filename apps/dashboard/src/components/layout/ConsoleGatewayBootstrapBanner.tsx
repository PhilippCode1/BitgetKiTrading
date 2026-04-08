import Link from "next/link";
import { Suspense } from "react";

import { IssueCenterQuickActions } from "@/components/console/IssueCenterQuickActions";
import type { GatewayBootstrapProbeResult } from "@/lib/gateway-bootstrap-probe";
import { getServerTranslator } from "@/lib/i18n/server-translate";

type Props = Readonly<{
  probe: GatewayBootstrapProbeResult;
}>;

/**
 * Eine zentrale Warnung nach aktiver Bootstrap-Diagnose statt identischer Panel-Fehler pro Widget.
 */
export async function ConsoleGatewayBootstrapBanner({ probe }: Props) {
  if (probe.rootCause === "ok") return null;
  const t = await getServerTranslator();
  const title = t(`console.bootstrap.${probe.rootCause}.title`);
  const body = t(`console.bootstrap.${probe.rootCause}.body`);
  return (
    <div className="console-bootstrap-banner" role="alert">
      <div className="console-bootstrap-banner__inner">
        <p className="console-bootstrap-banner__title">
          <strong>{title}</strong>
        </p>
        <p className="console-bootstrap-banner__body muted small">{body}</p>
        {probe.detail && probe.detail !== "ok" ? (
          <pre className="console-bootstrap-banner__pre small muted">
            {probe.detail}
          </pre>
        ) : null}
        <p className="console-bootstrap-banner__links small">
          <Link
            href="/api/dashboard/edge-status"
            target="_blank"
            rel="noreferrer"
          >
            {t("console.bootstrap.edgeStatusLink")}
          </Link>
        </p>
        <Suspense fallback={null}>
          <IssueCenterQuickActions />
        </Suspense>
      </div>
    </div>
  );
}
