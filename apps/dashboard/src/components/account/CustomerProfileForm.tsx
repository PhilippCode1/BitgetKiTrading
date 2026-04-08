"use client";

import { useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  initialDisplayName: string | null;
}>;

export function CustomerProfileForm({ initialDisplayName }: Props) {
  const { t } = useI18n();
  const [name, setName] = useState(initialDisplayName ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await fetch("/api/dashboard/commerce/customer/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: name.trim() === "" ? null : name.trim(),
        }),
      });
      if (!res.ok) {
        setErr(t("account.profile.saveErr"));
        return;
      }
      setMsg(t("account.profile.saved"));
    } catch {
      setErr(t("account.profile.saveErr"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="account-profile-form panel"
      onSubmit={(e) => void onSubmit(e)}
    >
      <label className="account-profile-label" htmlFor="display-name">
        {t("account.profile.displayLabel")}
      </label>
      <input
        id="display-name"
        className="account-profile-input"
        maxLength={120}
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoComplete="nickname"
      />
      <p className="muted small">{t("account.profile.displayHint")}</p>
      {err ? (
        <p className="msg-err" role="alert">
          {err}
        </p>
      ) : null}
      {msg ? (
        <p className="msg-ok" role="status">
          {msg}
        </p>
      ) : null}
      <button type="submit" className="public-btn primary" disabled={busy}>
        {busy ? t("account.profile.saving") : t("account.profile.save")}
      </button>
    </form>
  );
}
