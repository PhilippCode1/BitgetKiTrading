"use client";

import { useState } from "react";

import { LOCALE_LABELS, type Locale } from "@/lib/i18n/config";

import { useI18n } from "./I18nProvider";

type Props = Readonly<{
  className?: string;
}>;

export function LocaleSwitcher({ className }: Props) {
  const { locale, setLocale, t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onChange(next: Locale) {
    if (next === locale) return;
    setBusy(true);
    setErr(null);
    try {
      await setLocale(next);
    } catch {
      setErr(t("errors.generic"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={className ?? "dash-locale-switcher"}>
      <span className="muted small" style={{ marginRight: 6 }}>
        {t("console.localeSwitcher")}:
      </span>
      {(["de", "en"] as const).map((loc) => (
        <button
          key={loc}
          type="button"
          className={
            locale === loc ? "dash-locale-btn active" : "dash-locale-btn"
          }
          disabled={busy}
          onClick={() => void onChange(loc)}
          aria-pressed={locale === loc}
        >
          {LOCALE_LABELS[loc]}
        </button>
      ))}
      {err ? <span className="msg-err small">!</span> : null}
    </div>
  );
}
