"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { consolePath } from "@/lib/console-paths";

type Capabilities = {
  checkout_enabled?: boolean;
  environment?: string;
  methods?: {
    id: string;
    label: string;
    enabled: boolean;
    providers?: string[];
  }[];
  providers?: {
    stripe?: { enabled?: boolean };
    mock?: { enabled?: boolean };
  };
};

function readErr(res: Response, fallback: string): Promise<string> {
  return res.text().then((t) => {
    try {
      const j = JSON.parse(t) as {
        detail?: unknown;
        error?: { message?: string };
      };
      if (j.detail !== undefined && j.detail !== null) return String(j.detail);
      if (j.error?.message) return String(j.error.message);
    } catch {
      /* plain */
    }
    return t || fallback;
  });
}

export function DepositCheckoutPanel() {
  const { t } = useI18n();
  const [cap, setCap] = useState<Capabilities | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [amount, setAmount] = useState("10");
  const [provider, setProvider] = useState<"mock" | "stripe">("mock");
  const [intentId, setIntentId] = useState<string | null>(null);
  const [intentStatus, setIntentStatus] = useState<string | null>(null);

  const loadCaps = useCallback(async () => {
    setLoadErr(null);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/payments/capabilities",
        {
          cache: "no-store",
        },
      );
      if (!res.ok) {
        setLoadErr(await readErr(res, t("account.deposit.capLoadErr")));
        return;
      }
      const j = (await res.json()) as Capabilities;
      setCap(j);
      if (j.providers?.stripe?.enabled && !j.providers?.mock?.enabled) {
        setProvider("stripe");
      }
    } catch (e) {
      setLoadErr(
        e instanceof Error ? e.message : t("account.deposit.capLoadErr"),
      );
    }
  }, [t]);

  useEffect(() => {
    void loadCaps();
  }, [loadCaps]);

  const refreshIntent = async (id: string) => {
    const res = await fetch(
      `/api/dashboard/commerce/customer/payments/deposit/intent/${encodeURIComponent(id)}`,
      {
        cache: "no-store",
      },
    );
    if (!res.ok) return;
    const j = (await res.json()) as { intent?: { status?: string } };
    if (j.intent?.status) setIntentStatus(j.intent.status);
  };

  const startCheckout = async () => {
    setActionErr(null);
    setBusy(true);
    setIntentId(null);
    setIntentStatus(null);
    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt < 0.5) {
      setActionErr(t("account.deposit.amountErr"));
      setBusy(false);
      return;
    }
    const idem = crypto.randomUUID();
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/payments/deposit/checkout",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": idem,
          },
          body: JSON.stringify({
            provider,
            amount_list_usd: amt,
            currency: "USD",
          }),
        },
      );
      if (!res.ok) {
        setActionErr(await readErr(res, t("account.deposit.startErr")));
        setBusy(false);
        return;
      }
      const j = (await res.json()) as {
        intent_id?: string;
        checkout_url?: string | null;
        status?: string;
        idempotent_replay?: boolean;
      };
      if (j.intent_id) setIntentId(j.intent_id);
      if (j.intent_id) void refreshIntent(j.intent_id);
      const url = j.checkout_url;
      if (typeof url === "string" && url.length > 0) {
        window.location.assign(url);
        return;
      }
      if (j.status === "succeeded") {
        setIntentStatus("succeeded");
      }
    } catch (e) {
      setActionErr(
        e instanceof Error ? e.message : t("account.deposit.startErr"),
      );
    } finally {
      setBusy(false);
    }
  };

  const completeMock = async () => {
    if (!intentId) return;
    setActionErr(null);
    setBusy(true);
    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/payments/deposit/mock-complete",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intent_id: intentId }),
        },
      );
      if (!res.ok) {
        setActionErr(await readErr(res, t("account.deposit.mockErr")));
        setBusy(false);
        return;
      }
      await refreshIntent(intentId);
    } catch (e) {
      setActionErr(
        e instanceof Error ? e.message : t("account.deposit.mockErr"),
      );
    } finally {
      setBusy(false);
    }
  };

  if (loadErr) {
    return (
      <p className="msg-err" role="alert">
        {loadErr}
      </p>
    );
  }

  if (!cap) {
    return <p className="muted">{t("account.deposit.loading")}</p>;
  }

  if (!cap.checkout_enabled) {
    return (
      <div className="panel">
        <p className="muted">{t("account.deposit.disabled")}</p>
        <p className="muted small" style={{ marginTop: 12 }}>
          {t("account.deposit.disabledNext")}
        </p>
        <p style={{ marginTop: 12 }}>
          <Link
            href={consolePath("account/balance")}
            className="public-btn ghost"
          >
            {t("account.deposit.disabledLinkBalance")}
          </Link>
        </p>
      </div>
    );
  }

  const mockOn = cap.providers?.mock?.enabled === true;
  const stripeOn = cap.providers?.stripe?.enabled === true;
  const envRaw = (cap.environment ?? "").toString().trim().toLowerCase();
  const isLiveEnv = envRaw === "live";

  return (
    <div className="deposit-panel panel">
      {isLiveEnv ? (
        <div className="payment-env-rail--live" role="status">
          <strong>{t("account.deposit.envBannerLiveTitle")}</strong>
          <span> — {t("account.deposit.envBannerLiveBody")}</span>
        </div>
      ) : (
        <div className="warn-banner" role="status">
          <strong>{t("account.deposit.envBannerSandboxTitle")}</strong>
          <span> — {t("account.deposit.envBannerSandboxBody")}</span>
        </div>
      )}
      <p className="muted small">
        {t("account.deposit.env")}: <strong>{cap.environment ?? "—"}</strong>
      </p>
      {cap.methods && cap.methods.length > 0 ? (
        <div className="table-wrap" style={{ marginTop: "1rem" }}>
          <table className="data-table data-table--dense">
            <thead>
              <tr>
                <th>{t("account.deposit.thMethod")}</th>
                <th>{t("account.deposit.thStatus")}</th>
              </tr>
            </thead>
            <tbody>
              {cap.methods.map((m) => (
                <tr key={m.id}>
                  <td>{m.label}</td>
                  <td>
                    {m.enabled
                      ? t("account.deposit.on")
                      : t("account.deposit.off")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="form-block" style={{ marginTop: "1.25rem" }}>
        <label className="form-label" htmlFor="deposit-amt">
          {t("account.deposit.amountLabel")}
        </label>
        <input
          id="deposit-amt"
          className="form-input"
          type="number"
          min={0.5}
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <label
          className="form-label"
          htmlFor="deposit-prov"
          style={{ marginTop: "0.75rem" }}
        >
          {t("account.deposit.providerLabel")}
        </label>
        <select
          id="deposit-prov"
          className="form-input"
          value={provider}
          onChange={(e) => setProvider(e.target.value as "mock" | "stripe")}
        >
          {mockOn ? <option value="mock">mock (sandbox)</option> : null}
          {stripeOn ? <option value="stripe">Stripe Checkout</option> : null}
        </select>
        {!mockOn && !stripeOn ? (
          <p className="msg-err" role="alert" style={{ marginTop: "0.75rem" }}>
            {t("account.deposit.noProvider")}
          </p>
        ) : null}
        <button
          type="button"
          className="public-btn primary"
          style={{ marginTop: "1rem" }}
          disabled={busy || (!mockOn && !stripeOn)}
          onClick={() => void startCheckout()}
        >
          {t("account.deposit.start")}
        </button>
      </div>

      {actionErr ? (
        <p className="msg-err" role="alert" style={{ marginTop: "0.75rem" }}>
          {actionErr}
        </p>
      ) : null}

      {intentId ? (
        <p className="muted small" style={{ marginTop: "1rem" }}>
          {t("account.deposit.intent")}:{" "}
          <span className="mono-small">{intentId}</span>
          {intentStatus ? (
            <>
              {" "}
              — {t("account.deposit.status")}: <strong>{intentStatus}</strong>
            </>
          ) : null}
        </p>
      ) : null}

      {provider === "mock" && intentId && intentStatus !== "succeeded" ? (
        <button
          type="button"
          className="public-btn ghost"
          disabled={busy}
          onClick={() => void completeMock()}
        >
          {t("account.deposit.mockComplete")}
        </button>
      ) : null}

      {intentStatus === "succeeded" ? (
        <p className="msg-ok" style={{ marginTop: "0.75rem" }}>
          {t("account.deposit.done")}
        </p>
      ) : null}
    </div>
  );
}
