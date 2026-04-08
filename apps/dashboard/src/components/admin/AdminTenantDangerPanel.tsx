"use client";

import { useCallback, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

const LIFECYCLE_OPTIONS = [
  "invited",
  "registered",
  "trial_active",
  "trial_expired",
  "contract_pending",
  "contract_signed_waiting_admin",
  "live_approved",
  "suspended",
  "cancelled",
] as const;

type Props = Readonly<{ tenantId: string }>;

async function commerceMutate(
  method: string,
  path: string,
  payload: unknown,
): Promise<{ ok: boolean; status: number; text: string }> {
  const res = await fetch("/api/dashboard/admin/commerce-mutation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, path, payload }),
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, text };
}

export function AdminTenantDangerPanel({ tenantId }: Props) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [lifeTo, setLifeTo] = useState<string>(LIFECYCLE_OPTIONS[0]);
  const [lifeReason, setLifeReason] = useState("");
  const [lifeConfirm, setLifeConfirm] = useState("");

  const [walletDelta, setWalletDelta] = useState("");
  const [walletReason, setWalletReason] = useState("admin_adjustment");
  const [walletConfirm, setWalletConfirm] = useState("");

  const [emailVerified, setEmailVerified] = useState(true);
  const [emailConfirm, setEmailConfirm] = useState("");

  const [dunningStage, setDunningStage] = useState("none");
  const [dunningConfirm, setDunningConfirm] = useState("");

  const run = useCallback(
    async (
      label: string,
      fn: () => Promise<{ ok: boolean; status: number; text: string }>,
    ) => {
      setBusy(true);
      setMsg(null);
      try {
        const r = await fn();
        if (r.ok) {
          setMsg(`${label}: OK`);
        } else {
          setMsg(`${label}: HTTP ${r.status} — ${r.text.slice(0, 400)}`);
        }
      } catch (e) {
        setMsg(`${label}: ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const dunningPath = `/v1/commerce/admin/billing/tenant/${encodeURIComponent(tenantId)}/dunning`;

  return (
    <div className="panel admin-danger-panel">
      <h2>{t("pages.adminHub.danger.title")}</h2>
      <p className="muted small">{t("pages.adminHub.danger.lead")}</p>
      {msg ? (
        <p className="small" style={{ marginBottom: 12 }}>
          {msg}
        </p>
      ) : null}

      <section className="admin-danger-panel__block">
        <h3>{t("pages.adminHub.danger.lifecycle")}</h3>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.toStatus")}
          <select
            className="admin-danger-panel__input"
            value={lifeTo}
            onChange={(e) => setLifeTo(e.target.value)}
            disabled={busy}
          >
            {LIFECYCLE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.reasonOptional")}
          <input
            className="admin-danger-panel__input"
            value={lifeReason}
            onChange={(e) => setLifeReason(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.confirmTenant")}
          <input
            className="admin-danger-panel__input"
            value={lifeConfirm}
            onChange={(e) => setLifeConfirm(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="btn btn--danger"
          disabled={busy || lifeConfirm.trim() !== tenantId}
          onClick={() =>
            run("lifecycle", () =>
              commerceMutate(
                "POST",
                "/v1/commerce/admin/customer/lifecycle/transition",
                {
                  tenant_id: tenantId,
                  to_status: lifeTo,
                  reason_code: lifeReason.trim() || null,
                },
              ),
            )
          }
        >
          {t("pages.adminHub.danger.applyLifecycle")}
        </button>
      </section>

      <section className="admin-danger-panel__block">
        <h3>{t("pages.adminHub.danger.wallet")}</h3>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.deltaUsd")}
          <input
            className="admin-danger-panel__input"
            value={walletDelta}
            onChange={(e) => setWalletDelta(e.target.value)}
            disabled={busy}
            inputMode="decimal"
          />
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.reasonCode")}
          <input
            className="admin-danger-panel__input"
            value={walletReason}
            onChange={(e) => setWalletReason(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.confirmTenant")}
          <input
            className="admin-danger-panel__input"
            value={walletConfirm}
            onChange={(e) => setWalletConfirm(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="btn btn--danger"
          disabled={
            busy || walletConfirm.trim() !== tenantId || !walletReason.trim()
          }
          onClick={() => {
            const n = Number(walletDelta);
            if (Number.isNaN(n)) {
              setMsg(t("pages.adminHub.danger.invalidNumber"));
              return;
            }
            void run("wallet", () =>
              commerceMutate(
                "POST",
                "/v1/commerce/admin/customer/wallet/adjust",
                {
                  tenant_id: tenantId,
                  delta_list_usd: n,
                  reason_code: walletReason.trim(),
                },
              ),
            );
          }}
        >
          {t("pages.adminHub.danger.applyWallet")}
        </button>
      </section>

      <section className="admin-danger-panel__block">
        <h3>{t("pages.adminHub.danger.emailFlag")}</h3>
        <label className="admin-danger-panel__inline">
          <input
            type="checkbox"
            checked={emailVerified}
            onChange={(e) => setEmailVerified(e.target.checked)}
            disabled={busy}
          />{" "}
          {t("pages.adminHub.danger.emailVerified")}
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.confirmTenant")}
          <input
            className="admin-danger-panel__input"
            value={emailConfirm}
            onChange={(e) => setEmailConfirm(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="btn btn--danger"
          disabled={busy || emailConfirm.trim() !== tenantId}
          onClick={() =>
            run("email", () =>
              commerceMutate(
                "POST",
                "/v1/commerce/admin/customer/lifecycle/set-email-verified",
                {
                  tenant_id: tenantId,
                  email_verified: emailVerified,
                },
              ),
            )
          }
        >
          {t("pages.adminHub.danger.applyEmail")}
        </button>
      </section>

      <section className="admin-danger-panel__block">
        <h3>{t("pages.adminHub.danger.dunning")}</h3>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.dunningStage")}
          <input
            className="admin-danger-panel__input"
            value={dunningStage}
            onChange={(e) => setDunningStage(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="admin-danger-panel__label">
          {t("pages.adminHub.danger.confirmTenant")}
          <input
            className="admin-danger-panel__input"
            value={dunningConfirm}
            onChange={(e) => setDunningConfirm(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="btn btn--danger"
          disabled={
            busy || dunningConfirm.trim() !== tenantId || !dunningStage.trim()
          }
          onClick={() =>
            run("dunning", () =>
              commerceMutate("PATCH", dunningPath, {
                dunning_stage: dunningStage.trim(),
              }),
            )
          }
        >
          {t("pages.adminHub.danger.applyDunning")}
        </button>
      </section>
    </div>
  );
}
