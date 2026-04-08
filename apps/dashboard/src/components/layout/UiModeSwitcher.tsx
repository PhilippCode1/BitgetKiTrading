"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { UiMode } from "@/lib/dashboard-prefs";

type Props = Readonly<{
  initialMode: UiMode;
}>;

export function UiModeSwitcher({ initialMode }: Props) {
  const { t } = useI18n();
  const router = useRouter();
  const [mode, setMode] = useState<UiMode>(initialMode);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    const next: UiMode = mode === "simple" ? "pro" : "simple";
    setBusy(true);
    try {
      const res = await fetch("/api/dashboard/preferences/ui-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: next }),
      });
      if (!res.ok) return;
      setMode(next);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className="dash-ui-mode-btn"
      onClick={() => void toggle()}
      disabled={busy}
    >
      {mode === "simple" ? t("simple.switchToPro") : t("simple.switchToSimple")}
    </button>
  );
}
