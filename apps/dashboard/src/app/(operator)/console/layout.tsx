import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ClientBackgroundRevalidateBanner } from "@/components/console/ClientBackgroundRevalidateBanner";
import { DashboardQueryProvider } from "@/components/providers/DashboardQueryProvider";
import { ConsoleExecutionModeRibbon } from "@/components/layout/ConsoleExecutionModeRibbon";
import { ConsoleGatewayBootstrapBanner } from "@/components/layout/ConsoleGatewayBootstrapBanner";
import { ConsoleGatewayHeartbeat } from "@/components/layout/ConsoleGatewayHeartbeat";
import { ConsoleTelegramGate } from "@/components/layout/ConsoleTelegramGate";
import { ConsoleTrustBanner } from "@/components/layout/ConsoleTrustBanner";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { fetchSystemHealthBestEffort } from "@/lib/api";
import { getGatewayBootstrapProbeForRequest } from "@/lib/gateway-bootstrap-probe";
import type { ExecutionTierSnapshot } from "@/lib/types";
import { getRequestUiMode } from "@/lib/dashboard-prefs-server";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { resolveShowAdminNav } from "@/lib/operator-session";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getServerTranslator();
  return {
    title: t("console.metaTitle"),
    description: t("console.metaDescription"),
  };
}

type Props = Readonly<{ children: ReactNode }>;

export default async function OperatorConsoleLayout({ children }: Props) {
  const showAdminNav = await resolveShowAdminNav();
  const uiMode = await getRequestUiMode();
  const probe = await getGatewayBootstrapProbeForRequest();
  const t = await getServerTranslator();
  let executionTier: ExecutionTierSnapshot | null = null;
  let healthLoadHint: string | null = null;
  const probeBlocks = probe.rootCause !== "ok";
  if (!probeBlocks) {
    const { health, error } = await fetchSystemHealthBestEffort();
    if (error) {
      const hint = t(`ui.fetchError.${error.kind}.body`);
      healthLoadHint = hint;
    }
    if (health) {
      const rt = health.execution?.execution_runtime as
        | {
            execution_tier?: ExecutionTierSnapshot;
            executionTier?: ExecutionTierSnapshot;
          }
        | undefined;
      executionTier = rt?.execution_tier ?? rt?.executionTier ?? null;
    }
  }
  const healthErr = probeBlocks || Boolean(healthLoadHint);
  return (
    <DashboardShell
      showAdminNav={showAdminNav}
      uiMode={uiMode}
      topBarExtra={
        <ConsoleGatewayHeartbeat
          labelOk={t("ui.incident.heartbeatOk")}
          labelDegraded={t("ui.incident.heartbeatDegraded")}
          labelChecking={t("ui.incident.heartbeatChecking")}
          liveSseLabels={{
            CONNECTING: t("ui.incident.liveSseCONNECTING"),
            CONNECTED: t("ui.incident.liveSseCONNECTED"),
            DISCONNECTED: t("ui.incident.liveSseDISCONNECTED"),
            RECONNECTING: t("ui.incident.liveSseRECONNECTING"),
            GAVE_UP: t("ui.incident.liveSseGAVE_UP"),
          }}
        />
      }
    >
      <ConsoleGatewayBootstrapBanner probe={probe} />
      <ClientBackgroundRevalidateBanner />
      <ConsoleExecutionModeRibbon
        tier={executionTier}
        healthError={healthErr}
        healthLoadHint={healthLoadHint}
      />
      <ConsoleTrustBanner />
      <ConsoleTelegramGate>
        <DashboardQueryProvider>{children}</DashboardQueryProvider>
      </ConsoleTelegramGate>
    </DashboardShell>
  );
}
