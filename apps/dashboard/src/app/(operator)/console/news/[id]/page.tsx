import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { fetchNewsDetail } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import {
  diagnosticFromSearchParams,
  type ConsoleSearchParams,
} from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";
import { formatTsMs } from "@/lib/format";

export const dynamic = "force-dynamic";

type P = { id: string };

export default async function NewsDetailPage(props: {
  params: P | Promise<P>;
  searchParams?: ConsoleSearchParams | Promise<ConsoleSearchParams>;
}) {
  const sp = await Promise.resolve(props.searchParams ?? {});
  const diagnostic = diagnosticFromSearchParams(sp);
  const t = await getServerTranslator();
  const { id } = await Promise.resolve(props.params);
  let row: import("@/lib/types").NewsDetail | null = null;
  let err: string | null = null;
  try {
    row = await fetchNewsDetail(id);
  } catch (e) {
    err = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  if (err || !row) {
    return (
      <>
        <Header title={t("pages.news.title")} />
        <div className="panel" role="status">
          {err ? (
            <PanelDataIssue err={err} diagnostic={diagnostic} t={t} />
          ) : (
            <div className="console-fetch-notice console-fetch-notice--soft">
              <p className="console-fetch-notice__title">
                {t("pages.newsDetail.notFoundTitle")}
              </p>
              <p className="muted small">{t("pages.newsDetail.notFound")}</p>
            </div>
          )}
          <Link
            href={consolePath("news")}
            className="public-btn ghost"
            style={{ marginTop: 12, display: "inline-block" }}
          >
            ← {t("pages.newsDetail.backToList")}
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <Header
        title={row.title ?? t("pages.news.title")}
        subtitle={row.source ?? ""}
      />
      <p>
        <Link href={consolePath("news")}>
          ← {t("pages.newsDetail.backToList")}
        </Link>{" "}
        {row.url ? (
          <>
            ·{" "}
            <a href={row.url} target="_blank" rel="noreferrer">
              {t("pages.newsDetail.originalLink")}
            </a>
          </>
        ) : null}
      </p>
      <div className="panel">
        <p>
          {t("pages.newsDetail.metaLine", {
            score: row.score_0_100,
            sentiment: row.sentiment ?? "—",
            impact: row.impact_window ?? "—",
          })}
        </p>
        <p className="muted">
          {t("pages.newsDetail.publishedLabel")}:{" "}
          {formatTsMs(row.published_ts_ms)}
        </p>
        <h2>{t("pages.newsDetail.summaryTitle")}</h2>
        <p className="explain">{row.description ?? "—"}</p>
        {row.content ? (
          <>
            <h2>{t("pages.newsDetail.contentExcerptTitle")}</h2>
            <p className="explain">{row.content.slice(0, 4000)}</p>
          </>
        ) : null}
      </div>
    </>
  );
}
