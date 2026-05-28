"use client";

import Markdown from "react-markdown";

import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  markdown: string | null | undefined;
}>;

export function ExplainMarkdown({ markdown }: Props) {
  const { t } = useI18n();
  if (!markdown) {
    return <p className="muted">{t("pages.signals.explain.noLongDescription")}</p>;
  }
  return (
    <div className="markdown-body">
      <Markdown>{markdown}</Markdown>
    </div>
  );
}
