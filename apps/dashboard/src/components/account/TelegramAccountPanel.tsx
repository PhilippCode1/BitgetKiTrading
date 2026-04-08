"use client";

import { useCallback, useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

const NOTIFY_PREF_KEYS = [
  "notify_orders_demo",
  "notify_orders_live",
  "notify_billing",
  "notify_contract",
  "notify_risk",
  "notify_ai_tip",
] as const;

type NotifyPrefs = Record<(typeof NOTIFY_PREF_KEYS)[number], boolean>;

function prefLabelKey(k: (typeof NOTIFY_PREF_KEYS)[number]): string {
  const m: Record<string, string> = {
    notify_orders_demo: "account.telegram.prefDemoOrders",
    notify_orders_live: "account.telegram.prefLiveOrders",
    notify_billing: "account.telegram.prefBilling",
    notify_contract: "account.telegram.prefContract",
    notify_risk: "account.telegram.prefRisk",
    notify_ai_tip: "account.telegram.prefAiTip",
  };
  return m[k] ?? k;
}

type Onboarding = {
  connected?: boolean;
  verified_ts?: string | null;
  chat_ref_masked?: string | null;
  pending_link_expires_at?: string | null;
  bot_username_configured?: boolean;
  console_telegram_required?: boolean;
  migration_required?: boolean;
  deep_link_template?: string | null;
};

export function TelegramAccountPanel() {
  const { t } = useI18n();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [integration, setIntegration] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<"load" | "link" | "test" | null>("load");
  const [info, setInfo] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<NotifyPrefs | null>(null);
  const [prefsErr, setPrefsErr] = useState<string | null>(null);
  const [prefsBusy, setPrefsBusy] = useState(false);
  const [prefsLoading, setPrefsLoading] = useState(true);

  const reload = useCallback(async () => {
    setBusy("load");
    setErr(null);
    try {
      const res = await fetch("/api/dashboard/commerce/customer/integrations", {
        cache: "no-store",
      });
      if (!res.ok) {
        setErr(t("account.telegram.loadErr"));
        setOnboarding(null);
        return;
      }
      const data = (await res.json()) as {
        telegram_onboarding?: Onboarding;
        integration?: Record<string, unknown>;
      };
      setOnboarding(data.telegram_onboarding ?? {});
      setIntegration((data.integration as Record<string, unknown>) ?? null);
    } catch {
      setErr(t("account.telegram.loadErr"));
    } finally {
      setBusy(null);
    }
  }, [t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const loadPrefs = useCallback(async () => {
    setPrefsErr(null);
    setPrefsLoading(true);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/integrations/telegram/notify-prefs",
        {
          cache: "no-store",
        },
      );
      if (!res.ok) {
        setPrefs(null);
        setPrefsErr(t("account.telegram.prefsLoadErr"));
        return;
      }
      const data = (await res.json()) as { prefs?: Partial<NotifyPrefs> };
      const p = data.prefs;
      if (!p) {
        setPrefs(null);
        setPrefsErr(t("account.telegram.prefsLoadErr"));
        return;
      }
      const next = {} as NotifyPrefs;
      for (const k of NOTIFY_PREF_KEYS) {
        next[k] = Boolean(p[k]);
      }
      setPrefs(next);
    } catch {
      setPrefs(null);
      setPrefsErr(t("account.telegram.prefsLoadErr"));
    } finally {
      setPrefsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadPrefs();
  }, [loadPrefs]);

  const togglePref = async (
    key: (typeof NOTIFY_PREF_KEYS)[number],
    checked: boolean,
  ) => {
    if (prefsBusy) return;
    setPrefsBusy(true);
    setPrefsErr(null);
    setInfo(null);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/integrations/telegram/notify-prefs",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [key]: checked }),
          cache: "no-store",
        },
      );
      if (!res.ok) {
        const raw = await res.text();
        setPrefsErr(raw || t("account.telegram.prefsSaveErr"));
        return;
      }
      const data = (await res.json()) as { prefs?: Partial<NotifyPrefs> };
      const p = data.prefs;
      if (p) {
        const next = {} as NotifyPrefs;
        for (const k of NOTIFY_PREF_KEYS) {
          next[k] = Boolean(p[k]);
        }
        setPrefs(next);
      }
      setInfo(t("account.telegram.prefsSaved"));
    } catch (e) {
      setPrefsErr(
        e instanceof Error ? e.message : t("account.telegram.prefsSaveErr"),
      );
    } finally {
      setPrefsBusy(false);
    }
  };

  const startLink = async () => {
    setBusy("link");
    setInfo(null);
    setErr(null);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/integrations/telegram/start-link",
        { method: "POST", cache: "no-store" },
      );
      const raw = await res.text();
      if (!res.ok) {
        setErr(raw || `${res.status}`);
        return;
      }
      const data = JSON.parse(raw) as {
        deep_link?: string;
        expires_at?: string;
      };
      if (data.deep_link) {
        window.open(data.deep_link, "_blank", "noopener,noreferrer");
        setInfo(
          data.expires_at
            ? t("account.telegram.openedWithExpiry", {
                expiry: data.expires_at,
              })
            : t("account.telegram.openedBot"),
        );
      }
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("account.telegram.loadErr"));
    } finally {
      setBusy(null);
    }
  };

  const sendTest = async () => {
    setBusy("test");
    setInfo(null);
    setErr(null);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/integrations/telegram/test",
        { method: "POST", cache: "no-store" },
      );
      const raw = await res.text();
      if (!res.ok) {
        setErr(raw || `${res.status}`);
        return;
      }
      setInfo(t("account.telegram.testOk"));
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("account.telegram.loadErr"));
    } finally {
      setBusy(null);
    }
  };

  const ob = onboarding;
  const integState =
    integration?.telegram_state != null
      ? String(integration.telegram_state)
      : "—";
  const integHint = integration?.telegram_hint_public
    ? String(integration.telegram_hint_public)
    : "—";
  const connectionLabel = ob?.connected
    ? t("account.telegram.connectionYes")
    : t("account.telegram.connectionNo");

  return (
    <>
      {err ? (
        <p className="msg-err" role="alert">
          {err}
        </p>
      ) : null}
      {prefsErr ? (
        <p className="msg-err" role="alert">
          {prefsErr}
        </p>
      ) : null}
      {info ? (
        <p className="msg-ok" role="status">
          {info}
        </p>
      ) : null}
      <div className="panel" aria-busy={busy === "load"} aria-live="polite">
        {busy === "load" ? (
          <p className="muted small" style={{ margin: 0 }}>
            {t("account.telegram.loadingPanel")}
          </p>
        ) : (
          <>
            {ob?.migration_required ? (
              <p className="msg-err" role="alert">
                {t("account.telegram.migration")}
              </p>
            ) : null}
            {ob?.console_telegram_required ? (
              <p className="muted" role="note">
                {t("account.telegram.requiredHint")}
              </p>
            ) : null}
            <ul className="news-list">
              <li>
                <strong>{t("account.telegram.connection")}:</strong>{" "}
                {connectionLabel}
              </li>
              <li>
                {t("account.telegram.verifiedAt")}:{" "}
                <strong>{ob?.verified_ts ?? "—"}</strong>
              </li>
              <li className="muted">
                {t("account.telegram.chatMasked")}: {ob?.chat_ref_masked ?? "—"}
              </li>
              <li className="muted">
                {t("account.telegram.pendingExpires")}:{" "}
                {ob?.pending_link_expires_at ?? "—"}
              </li>
              <li>
                {t("account.telegram.snapshotState")}:{" "}
                <strong>{integState}</strong>
              </li>
              <li className="muted">
                {t("account.telegram.hint")}: {integHint}
              </li>
            </ul>
            <div className="btn-row" style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className="btn-primary"
                disabled={
                  busy !== null ||
                  ob?.migration_required ||
                  !ob?.bot_username_configured
                }
                onClick={() => void startLink()}
              >
                {busy === "link"
                  ? t("account.telegram.startLinkBusy")
                  : t("account.telegram.startLink")}
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={
                  busy !== null || !ob?.connected || ob?.migration_required
                }
                onClick={() => void sendTest()}
              >
                {busy === "test"
                  ? t("account.telegram.testBusy")
                  : t("account.telegram.testMsg")}
              </button>
            </div>
            {!ob?.bot_username_configured ? (
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                {t("account.telegram.botMissing")}
              </p>
            ) : null}
            <hr style={{ margin: "1.25rem 0", opacity: 0.35 }} />
            <h3
              style={{
                fontSize: "1.05rem",
                margin: "0 0 0.5rem",
                fontWeight: 600,
              }}
            >
              {t("account.telegram.prefsHeading")}
            </h3>
            <p className="muted small" style={{ marginTop: 0 }}>
              {t("account.telegram.prefsHint")}
            </p>
            <p className="muted small">
              Bot: <code>/kunde_help</code>, <code>/prefs</code>,{" "}
              <code>/set_notify</code> …
            </p>
            {prefsLoading ? (
              <p className="muted small">
                {t("account.telegram.loadingPanel")}
              </p>
            ) : prefs ? (
              <ul className="news-list" style={{ marginTop: "0.75rem" }}>
                {NOTIFY_PREF_KEYS.map((k) => (
                  <li key={k}>
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={prefs[k]}
                        disabled={prefsBusy || Boolean(ob?.migration_required)}
                        onChange={(e) => void togglePref(k, e.target.checked)}
                      />
                      <span>{t(prefLabelKey(k))}</span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}
