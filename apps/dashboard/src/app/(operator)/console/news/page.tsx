import Link from "next/link";

import { PanelDataIssue } from "@/components/console/ConsoleFetchNotice";
import { Header } from "@/components/layout/Header";
import { NewsTable } from "@/components/tables/NewsTable";
import { fetchNewsScored } from "@/lib/api";
import { consolePath } from "@/lib/console-paths";
import { diagnosticFromSearchParams } from "@/lib/console-params";
import { getServerTranslator } from "@/lib/i18n/server-translate";

export const dynamic = "force-dynamic";

type SP = Record<string, string | string[] | undefined>;

function first(sp: SP, key: string): string | undefined {
  const v = sp[key];
  return Array.isArray(v) ? v[0] : v;
}

export default async function NewsPage({
  searchParams,
}: {
  searchParams: SP | Promise<SP>;
}) {
  const t = await getServerTranslator();
  const sp = await Promise.resolve(searchParams);
  const diagnostic = diagnosticFromSearchParams(sp);
  const minScoreRaw = first(sp, "min_score");
  const sentiment = first(sp, "sentiment");
  const minScore = minScoreRaw !== undefined ? Number(minScoreRaw) : 0;

  let data = { items: [] as import("@/lib/types").NewsScoredItem[], limit: 50 };
  let error: string | null = null;
  try {
    data = await fetchNewsScored({
      min_score: Number.isFinite(minScore) ? minScore : 0,
      sentiment,
      limit: 80,
    });
  } catch (e) {
    error = e instanceof Error ? e.message : t("errors.fallbackMessage");
  }

  const href = (q: Record<string, string>) => {
    const u = new URLSearchParams(q);
    return `${consolePath("news")}?${u.toString()}`;
  };

  return (
    <>
      <Header
        title={t("pages.news.title")}
        subtitle={t("pages.news.subtitle")}
      />
      <PanelDataIssue err={error} diagnostic={diagnostic} t={t} />
      <div className="panel">
        <h2>{t("pages.news.filterTitle")}</h2>
        <div className="filter-row">
          <span className="muted">{t("pages.news.minScoreLabel")}:</span>
          {[0, 50, 70, 90].map((s) => (
            <Link
              key={s}
              href={href({
                min_score: String(s),
                ...(sentiment ? { sentiment } : {}),
              })}
              className={minScore === s ? "active" : ""}
            >
              {s}
            </Link>
          ))}
        </div>
        <div className="filter-row">
          <span className="muted">{t("pages.news.sentimentLabel")}:</span>
          {["bullish", "bearish", "neutral", "unknown"].map((se) => (
            <Link
              key={se}
              href={href({
                min_score: String(minScore),
                sentiment: se,
              })}
              className={sentiment === se ? "active" : ""}
            >
              {se}
            </Link>
          ))}
          <Link
            href={`${consolePath("news")}?min_score=${minScore}`}
            className={!sentiment ? "active" : ""}
          >
            {t("pages.news.filterAll")}
          </Link>
        </div>
      </div>
      <NewsTable
        items={data.items}
        emptyMessage={t("pages.news.tableEmpty")}
        detailLinkLabel={t("pages.news.detailLink")}
      />
    </>
  );
}
