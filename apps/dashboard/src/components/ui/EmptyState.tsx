"use client";

import type { ReactNode } from "react";
import { Suspense } from "react";
import Link from "next/link";

import { ConsoleFetchNoticeActions } from "@/components/console/ConsoleFetchNoticeActions";
import { useI18n } from "@/components/i18n/I18nProvider";
import { ContentPanel } from "@/components/ui/ContentPanel";
import { SystemCommsPhaseStrip } from "@/components/system-comms/SystemCommsPhaseStrip";
import type { SystemCommsPhase } from "@/lib/system-communication";

export type EmptyStateCTA = Readonly<
  | { labelKey: string; href: string }
  | { labelKey: string; onClick: () => void }
>;

type EmptyStateIcon = "inbox" | "layers" | "activity" | "wallet";

type EmptyStateShared = Readonly<{
  /** Optional: eine klare Nächst-Schritts-Zeile (ohne nummerierte Liste). */
  nextStepKey?: string;
  /** Optionale nummerierte nächste Schritte (z. B. help.signals). */
  stepKeys?: readonly string[];
  /** Icon-Variante — feste, barrierearme SVG-Illustration. */
  icon?: EmptyStateIcon;
  className?: string;
  cta?: EmptyStateCTA;
  /** Beliebige Aktion (Button/Link) neben oder statt {@link cta}. */
  actionButton?: ReactNode;
  children?: ReactNode;
  commsPhase?: SystemCommsPhase;
  showActions?: boolean;
}>;

export type EmptyStateProps = Readonly<
  | (EmptyStateShared & {
      titleKey: string;
      descriptionKey: string;
    })
  | (EmptyStateShared & {
      title: ReactNode;
      description: ReactNode;
    })
>;

function iconSvg(k: EmptyStateIcon): ReactNode {
  const common = {
    className: "empty-state__icon-img",
    width: 48,
    height: 48,
    viewBox: "0 0 24 24",
    fill: "none",
    xmlns: "http://www.w3.org/2000/svg",
    "aria-hidden": true,
  } as const;

  switch (k) {
    case "layers":
      return (
        <svg {...common}>
          <rect
            x="4.5"
            y="3.5"
            width="15"
            height="5"
            rx="1.2"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.85"
          />
          <rect
            x="3.5"
            y="9"
            width="17"
            height="5.5"
            rx="1.2"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.65"
          />
          <rect
            x="2.5"
            y="15.5"
            width="19"
            height="5.5"
            rx="1.2"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.45"
          />
        </svg>
      );
    case "activity":
      return (
        <svg {...common}>
          <path
            d="M4.5 17.2 8 12.8l3 2.1 2.2-3.1 2.1 1.2 2.1-1.1"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.75"
          />
          <path
            d="M3.5 4.5h5v2h-5zM10.2 4.5h2.1v2h-2.1zM19.1 4.5h-3.4v2h3.4z"
            fill="currentColor"
            opacity="0.35"
          />
        </svg>
      );
    case "wallet":
      return (
        <svg {...common}>
          <rect
            x="3.2"
            y="6.5"
            width="17.5"
            height="12.5"
            rx="1.4"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.75"
          />
          <rect
            x="3.2"
            y="9.5"
            width="6"
            height="4"
            rx="0.8"
            fill="currentColor"
            opacity="0.2"
          />
        </svg>
      );
    case "inbox":
    default:
      return (
        <svg {...common}>
          <rect
            x="4"
            y="5.5"
            width="16"
            height="13.5"
            rx="1.5"
            stroke="currentColor"
            strokeWidth="1.2"
            opacity="0.6"
          />
          <path
            d="M3.5 8.2h2.1l1.1 2.4h5.1l1-2.4H20.5"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
            opacity="0.45"
          />
        </svg>
      );
  }
}

/**
 * Leerzustand: Icon, Titel, Beschreibung (i18n-Keys oder freie Nodes), optionale CTA/Action, Nächst-Schritte-Liste.
 */
export function EmptyState(props: EmptyStateProps) {
  const { t } = useI18n();
  const isI18n = "titleKey" in props;
  const titleNode = isI18n ? t(props.titleKey) : props.title;
  const descriptionNode = isI18n ? t(props.descriptionKey) : props.description;
  const {
    nextStepKey,
    stepKeys,
    icon = "inbox",
    className = "",
    cta,
    actionButton,
    children,
    commsPhase,
    showActions,
  } = props;
  const hasSteps = (stepKeys?.length ?? 0) > 0;
  return (
    <ContentPanel
      className={["empty-state", className].filter(Boolean).join(" ")}
      role="status"
    >
      {commsPhase ? <SystemCommsPhaseStrip phase={commsPhase} /> : null}
      <div className="empty-state__row">
        <div className="empty-state__icon" aria-hidden>
          {iconSvg(icon)}
        </div>
        <div className="empty-state__text">
          <h3 className="empty-state__title">{titleNode}</h3>
          <p className="empty-state__body muted">{descriptionNode}</p>
          {nextStepKey ? (
            <p className="empty-state__next muted small">{t(nextStepKey)}</p>
          ) : null}
        </div>
      </div>
      {hasSteps ? (
        <div>
          <p className="empty-state__steps-label muted small">
            {t("help.nextSteps")}
          </p>
          <ol className="empty-state__steps">
            {stepKeys!.map((k) => (
              <li key={k}>{t(k)}</li>
            ))}
          </ol>
        </div>
      ) : null}
      {children}
      {cta || actionButton ? (
        <div className="empty-state__cta empty-state__cta--actions">
          {cta ? (
            "href" in cta ? (
              <Link className="public-btn ghost" href={cta.href}>
                {t(cta.labelKey)}
              </Link>
            ) : (
              <button
                type="button"
                className="public-btn ghost"
                onClick={cta.onClick}
              >
                {t(cta.labelKey)}
              </button>
            )
          ) : null}
          {actionButton}
        </div>
      ) : null}
      {showActions ? (
        <div className="empty-state__actions">
          <Suspense fallback={null}>
            <ConsoleFetchNoticeActions />
          </Suspense>
        </div>
      ) : null}
    </ContentPanel>
  );
}
