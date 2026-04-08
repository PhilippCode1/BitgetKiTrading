"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  guidedWelcomeUrl,
  ONBOARDING_DEFAULT_RETURN,
} from "@/lib/onboarding-flow";
import { consolePath } from "@/lib/console-paths";

const STEP_IDS = ["start", "account", "demo", "chart", "ai", "safety"] as const;

type StepId = (typeof STEP_IDS)[number];

type StepLink = Readonly<{ href: string; labelKey: string }>;

function stepLinks(stepId: StepId): readonly StepLink[] | null {
  switch (stepId) {
    case "start":
      return [
        {
          href: consolePath("account/language"),
          labelKey: "onboarding.steps.start.openLanguage",
        },
      ];
    case "account":
      return [
        {
          href: consolePath("account"),
          labelKey: "onboarding.steps.account.open",
        },
      ];
    case "demo":
      return [
        {
          href: consolePath("paper"),
          labelKey: "onboarding.steps.demo.openPaper",
        },
        {
          href: consolePath("account/broker"),
          labelKey: "onboarding.steps.demo.openBroker",
        },
      ];
    case "chart":
      return [
        {
          href: consolePath("terminal"),
          labelKey: "onboarding.steps.chart.open",
        },
      ];
    case "ai":
      return [
        { href: consolePath("health"), labelKey: "onboarding.steps.ai.open" },
      ];
    case "safety":
      return [
        {
          href: consolePath("ops"),
          labelKey: "onboarding.steps.safety.openOps",
        },
        {
          href: consolePath("account"),
          labelKey: "onboarding.steps.safety.openAccount",
        },
      ];
    default:
      return null;
  }
}

export function OnboardingWizard() {
  const { t } = useI18n();
  const router = useRouter();
  const search = useSearchParams();
  const finalReturn = useMemo(() => {
    const r = search.get("returnTo")?.trim();
    if (r && r.startsWith("/")) return r;
    return ONBOARDING_DEFAULT_RETURN;
  }, [search]);

  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const stepId = STEP_IDS[step] ?? "start";
  const total = STEP_IDS.length;
  const isLast = step === total - 1;
  const links = stepLinks(stepId);

  async function finish(status: "complete" | "skipped") {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/onboarding/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        const j = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error || `HTTP ${res.status}`);
      }
      router.replace(finalReturn);
      router.refresh();
    } catch {
      setErr(t("onboarding.errorSave"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="onboarding-main">
      <div className="onboarding-card panel">
        <p className="onboarding-progress muted small">
          {t("onboarding.progress", { current: step + 1, total })}
        </p>
        <div className="onboarding-title-row">
          <h1>{t("onboarding.title")}</h1>
          <HelpHint
            briefKey="help.onboarding.brief"
            detailKey="help.onboarding.detail"
          />
        </div>
        <p className="onboarding-lead muted">{t("onboarding.subtitle")}</p>

        <div className="onboarding-skip-row">
          <button
            type="button"
            className="onboarding-link-btn"
            disabled={busy}
            onClick={() => void finish("skipped")}
          >
            {t("onboarding.skipNow")}
          </button>
        </div>

        {err ? (
          <p className="msg-err" role="alert">
            {err}
          </p>
        ) : null}

        <section className="onboarding-step panel" aria-live="polite">
          <h2 className="onboarding-step-title">
            {t(`onboarding.steps.${stepId}.title`)}
          </h2>
          <p className="onboarding-step-body">
            {t(`onboarding.steps.${stepId}.body`)}
          </p>
          <p className="muted small">{t(`onboarding.steps.${stepId}.next`)}</p>
          {links && links.length > 0 ? (
            <p
              className={
                links.length > 1
                  ? "onboarding-action-row onboarding-action-row--split"
                  : "onboarding-action-row"
              }
            >
              {links.map((l) => (
                <Link key={l.href} href={l.href} className="public-btn ghost">
                  {t(l.labelKey)}
                </Link>
              ))}
            </p>
          ) : null}
        </section>

        <div className="onboarding-nav-row">
          <button
            type="button"
            className="public-btn ghost"
            disabled={step === 0 || busy}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            {t("onboarding.back")}
          </button>
          {!isLast ? (
            <button
              type="button"
              className="public-btn primary"
              disabled={busy}
              onClick={() => setStep((s) => Math.min(total - 1, s + 1))}
            >
              {t("onboarding.next")}
            </button>
          ) : (
            <button
              type="button"
              className="public-btn primary"
              disabled={busy}
              onClick={() => void finish("complete")}
            >
              {t("onboarding.finish")}
            </button>
          )}
        </div>

        <p className="muted small onboarding-footnote">
          {t("onboarding.footerNote")}
        </p>
        <p className="muted small onboarding-reopen-hint">
          <Link href={guidedWelcomeUrl(finalReturn)}>
            {t("onboarding.reopenLanguage")}
          </Link>
        </p>
      </div>
    </main>
  );
}
