"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DepositCheckoutPanel } from "@/components/account/DepositCheckoutPanel";
import { useI18n } from "@/components/i18n/I18nProvider";
import { ProductMessageCard } from "@/components/product-messages/ProductMessageCard";
import { portalPath } from "@/lib/console-paths";
import { buildProductMessageFromFetchError } from "@/lib/product-messages";

type BalancePayload = Readonly<{
  available_usdt?: string | number;
  reserved_usdt?: string | number;
  currency?: string;
}>;

function asBalance(raw: unknown): BalancePayload | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const body = (o.body ?? o) as Record<string, unknown>;
  return {
    available_usdt:
      (body.available_usdt as string | number | undefined) ??
      (body.balance_usdt as string | number | undefined),
    reserved_usdt: body.reserved_usdt as string | number | undefined,
    currency: (body.currency as string | undefined) ?? "USDT",
  };
}

function paymentRows(raw: unknown): ReadonlyArray<Record<string, string>> {
  if (!raw || typeof raw !== "object") return [];
  const o = raw as Record<string, unknown>;
  const items = (o.items ?? o.payments ?? o.body) as unknown;
  if (!Array.isArray(items)) return [];
  return items
    .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
    .map((row) => ({
      id: String(row.id ?? row.payment_id ?? "—"),
      status: String(row.status ?? row.state ?? "—"),
      amount: String(row.amount_usdt ?? row.amount ?? "—"),
      created: String(row.created_at ?? row.ts ?? "—"),
    }));
}

async function readJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { raw: text };
  }
}

export function CustomerPortalBillingClient() {
  const { t } = useI18n();
  const [balance, setBalance] = useState<BalancePayload | null>(null);
  const [payments, setPayments] = useState<
    ReadonlyArray<Record<string, string>>
  >([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [balRes, payRes] = await Promise.all([
        fetch("/api/dashboard/commerce/customer/balance", { cache: "no-store" }),
        fetch("/api/dashboard/commerce/customer/payments?limit=20", {
          cache: "no-store",
        }),
      ]);
      if (!balRes.ok) {
        throw new Error(
          balRes.status === 401
            ? t("customerPortal.accountBilling.sessionRequired")
            : `${t("customerPortal.accountBilling.balanceError")} (${balRes.status})`,
        );
      }
      const balJson = await readJson(balRes);
      setBalance(asBalance(balJson));
      if (payRes.ok) {
        const payJson = await readJson(payRes);
        setPayments(paymentRows(payJson));
      } else {
        setPayments([]);
      }
    } catch (e) {
      setLoadError(e);
      setBalance(null);
      setPayments([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <p className="muted" role="status" aria-busy="true">
        {t("customerPortal.accountBilling.loading")}
      </p>
    );
  }

  if (loadError) {
    return (
      <ProductMessageCard
        message={buildProductMessageFromFetchError(loadError, t)}
        t={t}
        showTechnical={false}
        showActions={false}
      >
        <div className="app-error-fallback__actions">
          <button
            type="button"
            className="public-btn primary"
            onClick={() => void load()}
          >
            {t("ui.issueCenter.reload")}
          </button>
          <Link href={portalPath("trading")} className="public-btn ghost">
            {t("customerPortal.nav.trading")}
          </Link>
        </div>
      </ProductMessageCard>
    );
  }

  return (
    <>
      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.balanceHeading")}
        </h2>
        {balance ? (
          <dl className="customer-billing-dl">
            <div>
              <dt>{t("customerPortal.accountBilling.available")}</dt>
              <dd>
                {balance.available_usdt ?? "—"} {balance.currency ?? "USDT"}
              </dd>
            </div>
            <div>
              <dt>{t("customerPortal.accountBilling.reserved")}</dt>
              <dd>
                {balance.reserved_usdt ?? "—"} {balance.currency ?? "USDT"}
              </dd>
            </div>
          </dl>
        ) : (
          <p className="muted">{t("customerPortal.accountBilling.balanceEmpty")}</p>
        )}
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.paymentsHeading")}
        </h2>
        {payments.length === 0 ? (
          <p className="muted">{t("customerPortal.accountBilling.paymentsEmpty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--dense">
              <thead>
                <tr>
                  <th>{t("customerPortal.accountBilling.colId")}</th>
                  <th>{t("customerPortal.accountBilling.colStatus")}</th>
                  <th>{t("customerPortal.accountBilling.colAmount")}</th>
                  <th>{t("customerPortal.accountBilling.colCreated")}</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((row) => (
                  <tr key={row.id}>
                    <td className="mono-small">{row.id}</td>
                    <td>{row.status}</td>
                    <td>{row.amount}</td>
                    <td>{row.created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="muted" style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
          {t("customerPortal.accountBilling.depositHeading")}
        </h2>
        <p className="muted small">{t("customerPortal.accountBilling.depositLead")}</p>
        <DepositCheckoutPanel />
      </section>
    </>
  );
}
