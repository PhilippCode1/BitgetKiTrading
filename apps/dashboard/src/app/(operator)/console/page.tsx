import Link from "next/link";

import { HealthSnapshotLoadNotice } from "@/components/console/HealthSnapshotLoadNotice";
import { Header } from "@/components/layout/Header";
import { LiveDataSituationBar } from "@/components/live-data/LiveDataSituationBar";
import { ONBOARDING_NAV_HREF } from "@/lib/onboarding-flow";
import { CONSOLE_BASE, consolePath } from "@/lib/console-paths";
import { fetchSystemHealthBestEffort } from "@/lib/api";
import { diagnosticFromSearchParams } from "@/lib/console-params";
import { buildLiveDataSurfaceModelFromHealth } from "@/lib/live-data-surface-model";
import { getRequestUiMode } from "@/lib/dashboard-prefs-server";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type SimpleTile = Readonly<{
  segment?: string;
  href?: string;
  titleKey: string;
  bodyKey: string;
  tagKey?: string;
  primary?: boolean;
}>;

type ProTile = Readonly<{
  segment?: string;
  href?: string;
  titleKey: string;
  bodyKey: string;
  tagKey?: string;
}>;

type ProSection = Readonly<{
  headingKey: string;
  tiles: readonly ProTile[];
}>;

const SIMPLE_TILES: SimpleTile[] = [
  {
    segment: "terminal",
    titleKey: "consoleHome.simple.tileChart.title",
    bodyKey: "consoleHome.simple.tileChart.body",
    tagKey: "consoleHome.simple.tileChart.tag",
    primary: true,
  },
  {
    segment: "health",
    titleKey: "consoleHome.simple.ai.title",
    bodyKey: "consoleHome.simple.ai.body",
    tagKey: "consoleHome.simple.ai.tag",
  },
  {
    segment: "paper",
    titleKey: "consoleHome.simple.paper.title",
    bodyKey: "consoleHome.simple.paper.body",
    tagKey: "consoleHome.simple.paper.tag",
  },
  {
    segment: "account",
    titleKey: "consoleHome.simple.account.title",
    bodyKey: "consoleHome.simple.account.body",
    tagKey: "consoleHome.simple.account.tag",
  },
  {
    segment: "signals",
    titleKey: "consoleHome.simple.signals.title",
    bodyKey: "consoleHome.simple.signals.body",
    tagKey: "consoleHome.simple.signals.tag",
  },
  {
    href: `${CONSOLE_BASE}/help`,
    titleKey: "consoleHome.simple.tileHelp.title",
    bodyKey: "consoleHome.simple.tileHelp.body",
    tagKey: "consoleHome.simple.tileHelp.tag",
  },
  {
    href: `${CONSOLE_BASE}/account/language`,
    titleKey: "consoleHome.simple.settings.title",
    bodyKey: "consoleHome.simple.settings.body",
  },
];

const PRO_SECTIONS: ProSection[] = [
  {
    headingKey: "consoleHome.pro.s1.heading",
    tiles: [
      {
        segment: "market-universe",
        titleKey: "consoleHome.pro.mu.title",
        bodyKey: "consoleHome.pro.mu.body",
      },
      {
        segment: "capabilities",
        titleKey: "consoleHome.pro.cap.title",
        bodyKey: "consoleHome.pro.cap.body",
      },
      {
        segment: "signals",
        titleKey: "consoleHome.pro.sig.title",
        bodyKey: "consoleHome.pro.sig.body",
      },
      {
        segment: "no-trade",
        titleKey: "consoleHome.pro.nt.title",
        bodyKey: "consoleHome.pro.nt.body",
      },
    ],
  },
  {
    headingKey: "consoleHome.pro.s3.heading",
    tiles: [
      {
        segment: "ops",
        titleKey: "consoleHome.pro.ops.title",
        bodyKey: "consoleHome.pro.ops.body",
        tagKey: "consoleHome.pro.ops.tag",
      },
      {
        segment: "terminal",
        titleKey: "consoleHome.pro.term.title",
        bodyKey: "consoleHome.pro.term.body",
      },
      {
        segment: "approvals",
        titleKey: "consoleHome.pro.appr.title",
        bodyKey: "consoleHome.pro.appr.body",
      },
      {
        segment: "health",
        titleKey: "consoleHome.pro.health.title",
        bodyKey: "consoleHome.pro.health.body",
      },
      {
        segment: "live-broker",
        titleKey: "consoleHome.pro.lb.title",
        bodyKey: "consoleHome.pro.lb.body",
      },
      {
        segment: "shadow-live",
        titleKey: "consoleHome.pro.sl.title",
        bodyKey: "consoleHome.pro.sl.body",
      },
      {
        segment: "paper",
        titleKey: "consoleHome.pro.pap.title",
        bodyKey: "consoleHome.pro.pap.body",
      },
    ],
  },
  {
    headingKey: "consoleHome.pro.s4.heading",
    tiles: [
      {
        segment: "learning",
        titleKey: "consoleHome.pro.learn.title",
        bodyKey: "consoleHome.pro.learn.body",
      },
      {
        segment: "strategies",
        titleKey: "consoleHome.pro.strat.title",
        bodyKey: "consoleHome.pro.strat.body",
      },
    ],
  },
  {
    headingKey: "consoleHome.pro.s5.heading",
    tiles: [
      {
        segment: "news",
        titleKey: "consoleHome.pro.news.title",
        bodyKey: "consoleHome.pro.news.body",
      },
      {
        segment: "usage",
        titleKey: "consoleHome.pro.use.title",
        bodyKey: "consoleHome.pro.use.body",
      },
      {
        segment: "integrations",
        titleKey: "consoleHome.pro.integ.title",
        bodyKey: "consoleHome.pro.integ.body",
      },
    ],
  },
  {
    headingKey: "consoleHome.pro.s6.heading",
    tiles: [
      {
        segment: "account",
        titleKey: "consoleHome.pro.acc.title",
        bodyKey: "consoleHome.pro.acc.body",
        tagKey: "consoleHome.pro.acc.tag",
      },
      {
        href: ONBOARDING_NAV_HREF,
        titleKey: "consoleHome.pro.onb.title",
        bodyKey: "consoleHome.pro.onb.body",
      },
      {
        href: `${CONSOLE_BASE}/help`,
        titleKey: "consoleHome.pro.helpHub.title",
        bodyKey: "consoleHome.pro.helpHub.body",
      },
    ],
  },
];

type ConsoleHomeSearchParams = Record<
  string,
  string | string[] | undefined
>;

export default async function ConsoleHomePage({
  searchParams,
}: {
  searchParams?: ConsoleHomeSearchParams | Promise<ConsoleHomeSearchParams>;
}) {
  const sp = await Promise.resolve(searchParams ?? {});
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const uiMode = await getRequestUiMode();

  if (uiMode === "simple") {
    const { health: simpleHealth, error: simpleHealthErr } =
      await fetchSystemHealthBestEffort();
    const simpleHomeHealthModel = simpleHealth
      ? buildLiveDataSurfaceModelFromHealth({ health: simpleHealth })
      : null;

    return (
      <>
        <Header
          title={t("consoleHome.simple.title")}
          subtitle={t("consoleHome.simple.subtitle")}
        />
        {simpleHomeHealthModel ? (
          <LiveDataSituationBar model={simpleHomeHealthModel} />
        ) : null}
        <div
          className="console-page-notice-stack"
          aria-label={t("console.pageNoticesGroupAria")}
        >
          <HealthSnapshotLoadNotice
            error={simpleHealthErr}
            diagnostic={diagnostic}
            t={t}
          />
        </div>
        <section className="panel console-ki-path-banner">
          <h2 className="console-ki-path-banner__title">
            {t("consoleHome.kiPathTitle")}
          </h2>
          <p className="muted small">{t("consoleHome.kiPathBody")}</p>
          <div className="console-ki-path-banner__actions">
            <Link href={consolePath("health")} className="public-btn primary">
              {t("consoleHome.kiPathCtaHealth")}
            </Link>
            <Link href={consolePath("signals")} className="public-btn ghost">
              {t("consoleHome.kiPathSecondary")}
            </Link>
            <Link href={consolePath("terminal")} className="public-btn ghost">
              {t("consoleHome.kiPathChart")}
            </Link>
          </div>
        </section>
        <p className="muted small" style={{ marginBottom: 16 }}>
          {t("consoleHome.simple.intro")}
        </p>
        <div className="console-tile-grid">
          {SIMPLE_TILES.map((tile) => {
            const href = tile.href ?? consolePath(tile.segment ?? "");
            const key = tile.href ?? tile.segment ?? tile.titleKey;
            return (
              <Link
                key={key}
                href={href}
                className={`console-tile${tile.primary ? " console-tile--primary" : ""}`}
              >
                <div className="console-tile-head">
                  <span className="console-tile-title">{t(tile.titleKey)}</span>
                  {tile.tagKey ? (
                    <span className="console-tile-tag">{t(tile.tagKey)}</span>
                  ) : null}
                </div>
                <p className="muted small">{t(tile.bodyKey)}</p>
              </Link>
            );
          })}
        </div>
        <p className="muted small" style={{ marginTop: 20 }}>
          {t("consoleHome.simple.proHint")}
        </p>
      </>
    );
  }

  const { health: proHealth, error: proHealthErr } =
    await fetchSystemHealthBestEffort();
  const homeHealthModel = proHealth
    ? buildLiveDataSurfaceModelFromHealth({ health: proHealth })
    : null;

  return (
    <>
      <Header
        title={t("consoleHome.pro.title")}
        subtitle={t("consoleHome.pro.subtitle")}
      />
      {homeHealthModel ? <LiveDataSituationBar model={homeHealthModel} /> : null}
      <div
        className="console-page-notice-stack"
        aria-label={t("console.pageNoticesGroupAria")}
      >
        <HealthSnapshotLoadNotice
          error={proHealthErr}
          diagnostic={diagnostic}
          t={t}
        />
      </div>
      <section className="panel console-ki-path-banner">
        <h2 className="console-ki-path-banner__title">
          {t("consoleHome.kiPathTitle")}
        </h2>
        <p className="muted small">{t("consoleHome.kiPathBody")}</p>
        <div className="console-ki-path-banner__actions">
          <Link href={consolePath("learning")} className="public-btn primary">
            {t("consoleHome.kiPathCta")}
          </Link>
          <Link href={consolePath("signals")} className="public-btn ghost">
            {t("consoleHome.kiPathSecondary")}
          </Link>
          <Link href={consolePath("health")} className="public-btn ghost">
            {t("console.nav.health")}
          </Link>
        </div>
      </section>
      {PRO_SECTIONS.map((section) => (
        <section
          key={section.headingKey}
          className="panel"
          style={{ marginBottom: 16 }}
        >
          <h2>{t(section.headingKey)}</h2>
          <div className="console-tile-grid">
            {section.tiles.map((tile) => {
              const href = tile.href ?? consolePath(tile.segment ?? "");
              const key = tile.href ?? tile.segment ?? tile.titleKey;
              return (
                <Link key={key} href={href} className="console-tile">
                  <div className="console-tile-head">
                    <span className="console-tile-title">
                      {t(tile.titleKey)}
                    </span>
                    {tile.tagKey ? (
                      <span className="console-tile-tag">{t(tile.tagKey)}</span>
                    ) : null}
                  </div>
                  <p className="muted small">{t(tile.bodyKey)}</p>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </>
  );
}
