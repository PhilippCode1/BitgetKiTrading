"use client";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { LiveNewsItem } from "@/lib/types";

type Props = {
  items: LiveNewsItem[];
  compact?: boolean;
};

const nk = (k: string) => `live.newsPanel.${k}` as const;

export function NewsPanel({ items, compact }: Props) {
  const { t } = useI18n();
  const list = compact ? items.slice(0, 5) : items;
  return (
    <div className="panel news-mini">
      <h2>{t(nk("title"))}</h2>
      <ul className="news-list">
        {list.length === 0 ? (
          <li className="muted">{t(nk("empty"))}</li>
        ) : (
          list.map((n) => (
            <li key={n.news_id || n.title}>
              <span className="news-title">{n.title}</span>
              {n.relevance_score != null ? (
                <span className="news-score"> · {n.relevance_score}</span>
              ) : null}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
