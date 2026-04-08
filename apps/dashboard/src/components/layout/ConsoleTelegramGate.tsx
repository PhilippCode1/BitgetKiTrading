"use client";

import type { ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";
import { publicEnv } from "@/lib/env";

const ACCOUNT_PREFIX = consolePath("account");

/**
 * Wenn aktiviert: ohne verknuepftes Telegram nur Bereich unter /console/account/*.
 */
export function ConsoleTelegramGate({
  children,
}: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { t } = useI18n();
  const required = publicEnv.commercialTelegramRequiredForConsole;
  const [ready, setReady] = useState(!required);

  useEffect(() => {
    if (!required) {
      return;
    }
    if (
      pathname === ACCOUNT_PREFIX ||
      pathname.startsWith(`${ACCOUNT_PREFIX}/`)
    ) {
      setReady(true);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          "/api/dashboard/commerce/customer/integrations",
          {
            cache: "no-store",
            signal: AbortSignal.timeout(15_000),
          },
        );
        if (!res.ok) {
          if (!cancelled) setReady(true);
          return;
        }
        const data = (await res.json()) as {
          telegram_onboarding?: { connected?: boolean };
        };
        if (cancelled) return;
        if (data.telegram_onboarding?.connected) {
          setReady(true);
        } else {
          router.replace(consolePath("account/telegram"));
        }
      } catch {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, required, router]);

  if (!ready) {
    return (
      <div
        className="panel muted"
        style={{ margin: "1rem" }}
        role="status"
        aria-live="polite"
      >
        {t("console.telegramGate.loading")}
      </div>
    );
  }
  return <>{children}</>;
}
