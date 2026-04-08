import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import type { ExecutionTierSnapshot } from "@/lib/types";

type Props = Readonly<{
  tier: ExecutionTierSnapshot | null | undefined;
  healthError?: boolean;
  /** Gateway-/Health-Fehlertext (gekürzt), nur wenn {@link healthError} und Abruf scheiterte */
  healthLoadHint?: string | null;
}>;

function ribbonClass(tier: ExecutionTierSnapshot | null | undefined): string {
  if (!tier) return "console-execution-tier--unknown";
  if (tier.automated_live_orders_enabled)
    return "console-execution-tier--danger";
  if (tier.trading_plane === "live") return "console-execution-tier--live";
  if (tier.trading_plane === "exchange_sandbox")
    return "console-execution-tier--sandbox";
  if (tier.trading_plane === "shadow") return "console-execution-tier--shadow";
  return "console-execution-tier--paper";
}

function ribbonHelpLinks(t: (k: string) => string) {
  return (
    <div className="console-execution-tier__links muted small">
      <Link href={consolePath("health")}>{t("console.executionTier.linkHealth")}</Link>
      <span className="console-execution-tier__sep">·</span>
      <Link href={consolePath("diagnostics")}>
        {t("console.executionTier.linkDiagnostics")}
      </Link>
      <span className="console-execution-tier__sep">·</span>
      <Link href={consolePath("self-healing")}>
        {t("console.executionTier.linkSelfHealing")}
      </Link>
    </div>
  );
}

export async function ConsoleExecutionModeRibbon({
  tier,
  healthError,
  healthLoadHint = null,
}: Props) {
  const t = await getServerTranslator();
  const base = "console-execution-tier";
  const mod = ribbonClass(tier ?? null);

  if (healthError) {
    return (
      <div
        className={`${base} ${base}--unknown`}
        role="status"
        aria-live="polite"
      >
        <span className="console-execution-tier__label">
          {t("console.executionTier.healthUnreachable")}
        </span>
        {healthLoadHint ? (
          <span className="console-execution-tier__hint muted small">
            {t("console.executionTier.healthFailedHint", { hint: healthLoadHint })}
          </span>
        ) : null}
        {ribbonHelpLinks(t)}
      </div>
    );
  }
  if (tier == null) {
    return (
      <div
        className={`${base} ${base}--unknown`}
        role="status"
        aria-live="polite"
      >
        <span className="console-execution-tier__label">
          {t("console.executionTier.tierMissing")}
        </span>
        {ribbonHelpLinks(t)}
      </div>
    );
  }

  const planeKey =
    `console.executionTier.planes.${tier.trading_plane}` as const;
  const deployKey = `console.executionTier.deploy.${tier.deployment}` as const;
  const planeLabel = t(planeKey);
  const deployLabel = t(deployKey);

  return (
    <div className={`${base} ${mod}`} role="status" aria-live="polite">
      <span className="console-execution-tier__label">
        {t("console.executionTier.title")}
      </span>
      <span
        className="console-execution-tier__value"
        title={tier.execution_mode}
      >
        {planeLabel}
      </span>
      <span className="console-execution-tier__sep">·</span>
      <span className="console-execution-tier__meta">{deployLabel}</span>
      {tier.bitget_demo_enabled ? (
        <>
          <span className="console-execution-tier__sep">·</span>
          <span className="console-execution-tier__flag">
            {t("console.executionTier.demoFlag")}
          </span>
        </>
      ) : null}
      {tier.automated_live_orders_enabled ? (
        <>
          <span className="console-execution-tier__sep">·</span>
          <strong className="console-execution-tier__warn">
            {t("console.executionTier.autoLiveWarn")}
          </strong>
        </>
      ) : null}
      <div className="console-execution-tier__row2 muted small">
        {t("console.executionTier.configLine", {
          executionMode: tier.execution_mode,
          strategyMode: tier.strategy_execution_mode,
        })}
      </div>
      {ribbonHelpLinks(t)}
    </div>
  );
}
