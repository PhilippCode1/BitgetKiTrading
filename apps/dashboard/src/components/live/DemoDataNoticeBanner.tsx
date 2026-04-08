"use client";

import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";
import { useI18n } from "@/components/i18n/I18nProvider";
import type { DemoDataNotice } from "@/lib/types";

type Props = {
  notice: DemoDataNotice | null | undefined;
};

export function DemoDataNoticeBanner({ notice }: Props) {
  const { t } = useI18n();
  if (!notice?.show_banner || !notice.reasons?.length) {
    return null;
  }
  return (
    <ConsoleFetchNotice
      variant="soft"
      title={t("live.terminal.demoDataTitle")}
      body={t("live.terminal.demoDataBody")}
      style={{ marginBottom: 12 }}
    >
      <ul className="console-fetch-notice__list muted small">
        {notice.reasons.map((code) => (
          <li key={code}>{t(`live.terminal.demoReason.${code}`)}</li>
        ))}
      </ul>
    </ConsoleFetchNotice>
  );
}
