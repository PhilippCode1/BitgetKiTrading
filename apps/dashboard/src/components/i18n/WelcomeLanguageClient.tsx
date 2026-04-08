"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { HelpHint } from "@/components/help/HelpHint";
import { useI18n } from "@/components/i18n/I18nProvider";
import {
  LOCALE_STORAGE_KEY,
  LOCALE_LABELS,
  type Locale,
} from "@/lib/i18n/config";
import { mirrorLocalePreferenceToServer } from "@/lib/client/best-effort-fetch";
import { CONSOLE_BASE } from "@/lib/console-paths";

function nextStepLabel(
  returnTo: string,
  t: (k: string, v?: Record<string, string | number | boolean>) => string,
): string {
  const r = returnTo.trim() || "/";
  if (r === "/" || r === "") return t("welcome.destHome");
  if (r.includes("/onboarding")) return t("welcome.destOnboarding");
  if (r === CONSOLE_BASE || r.startsWith(`${CONSOLE_BASE}/`))
    return t("welcome.destConsole");
  if (r.startsWith("/welcome")) return t("welcome.destLanguage");
  return t("welcome.destOther", {
    path: r.length > 56 ? `${r.slice(0, 54)}…` : r,
  });
}

/**
 * Schritt 1 vor dem Dashboard: bewusst zweisprachig (DE/EN), ohne abhaengig von bereits gesetzter Locale.
 * Speicherung: POST /api/locale (Cookie) + localStorage; optional Mirror /api/dashboard/preferences/locale.
 */
export function WelcomeLanguageClient() {
  const router = useRouter();
  const search = useSearchParams();
  const { t } = useI18n();
  const returnTo = search.get("returnTo")?.trim() || "/";
  const destLabel = nextStepLabel(returnTo, t);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function choose(locale: Locale) {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/locale", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale }),
      });
      if (!res.ok) {
        const j = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(j.error || `HTTP ${res.status}`);
      }
      try {
        localStorage.setItem(LOCALE_STORAGE_KEY, locale);
      } catch {
        /* private mode */
      }
      await mirrorLocalePreferenceToServer(locale);
      router.replace(returnTo.startsWith("/") ? returnTo : "/");
      router.refresh();
    } catch (e) {
      const code = e instanceof Error ? e.message : "";
      setErr(
        code === "unsupported_locale"
          ? t("errors.unsupportedLocale")
          : t("welcome.errorGeneric"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="welcome-gate">
      <div className="welcome-card panel">
        <div className="welcome-title-row">
          <h1>{t("welcome.title")}</h1>
          <HelpHint
            briefKey="help.welcome.brief"
            detailKey="help.welcome.detail"
          />
        </div>
        <p className="welcome-lead">{t("welcome.subtitle")}</p>
        <p className="muted small readable">{t("welcome.valueLead")}</p>
        <p className="muted small">{t("welcome.hintStorage")}</p>
        <p className="muted small">
          {t("welcome.nextStepLead", { label: destLabel })}
        </p>
        {err ? (
          <p className="msg-err" role="alert">
            {err}
          </p>
        ) : null}
        <div className="welcome-lang-row">
          {(["de", "en"] as const).map((loc) => (
            <button
              key={loc}
              type="button"
              className="public-btn primary welcome-lang-btn"
              disabled={busy}
              onClick={() => void choose(loc)}
            >
              {LOCALE_LABELS[loc]}
            </button>
          ))}
        </div>
      </div>
    </main>
  );
}
