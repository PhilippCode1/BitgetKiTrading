"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

const DEFAULT_TEMPLATE_KEY = "modul_mate_standard_v1";

type Row = Record<string, unknown>;

function gatewayContractsPath(suffix: string): string {
  const s = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return `/api/dashboard/gateway/v1/commerce/customer/contracts${s}`;
}

export function ContractWorkflowClient({
  initialTemplates,
  initialContracts,
  loadError,
}: {
  initialTemplates: Row[];
  initialContracts: Row[];
  loadError: string | null;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [docsByContract, setDocsByContract] = useState<Record<string, Row[]>>(
    {},
  );

  const openAwaitingSign = useMemo(() => {
    return initialContracts.find(
      (c) => String(c.status || "") === "awaiting_customer_sign",
    ) as Row | undefined;
  }, [initialContracts]);

  const loadDocuments = useCallback(
    async (contractId: string) => {
      const r = await fetch(gatewayContractsPath(`/${contractId}/documents`), {
        credentials: "same-origin",
      });
      const text = await r.text();
      if (!r.ok) {
        setMsg(text.slice(0, 200) || t("account.contract.errGeneric"));
        return;
      }
      try {
        const j = JSON.parse(text) as { documents?: Row[] };
        setDocsByContract((prev) => ({
          ...prev,
          [contractId]: j.documents ?? [],
        }));
      } catch {
        setMsg(t("account.contract.errGeneric"));
      }
    },
    [t],
  );

  const toggleExpand = useCallback(
    async (contractId: string) => {
      if (expanded === contractId) {
        setExpanded(null);
        return;
      }
      setExpanded(contractId);
      if (!docsByContract[contractId]) {
        await loadDocuments(contractId);
      }
    },
    [expanded, docsByContract, loadDocuments],
  );

  const postJson = useCallback(
    async (path: string, body?: Row) => {
      setBusy(path);
      setMsg(null);
      try {
        const r = await fetch(gatewayContractsPath(path), {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body ?? {}),
        });
        const text = await r.text();
        if (!r.ok) {
          setMsg(text.slice(0, 400) || t("account.contract.errGeneric"));
          return;
        }
        setMsg(t("account.contract.ok"));
        router.refresh();
      } catch {
        setMsg(t("account.contract.errGeneric"));
      } finally {
        setBusy(null);
      }
    },
    [router, t],
  );

  if (loadError) {
    return (
      <div className="panel">
        <p className="text-error">{loadError}</p>
        <p className="muted small">{t("account.contract.migrationHint")}</p>
      </div>
    );
  }

  return (
    <div className="panel">
      {msg ? <p className="small muted">{msg}</p> : null}

      <h3 className="account-section-title">
        {t("account.contract.templatesTitle")}
      </h3>
      {initialTemplates.length === 0 ? (
        <p className="muted small">{t("account.contract.migrationHint")}</p>
      ) : (
        <ul className="news-list operator-metric-list">
          {initialTemplates.map((tpl) => (
            <li key={`${String(tpl.template_key)}@${String(tpl.version)}`}>
              <strong>{String(tpl.title_de ?? tpl.template_key)}</strong> —{" "}
              <span className="mono-small">
                {String(tpl.template_key)} v{String(tpl.version)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <h3 className="account-section-title">
        {t("account.contract.contractsTitle")}
      </h3>
      <div
        className="account-contract-actions"
        style={{
          marginBottom: "1rem",
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <button
          type="button"
          className="btn secondary"
          disabled={busy !== null}
          onClick={() =>
            postJson("/start", {
              template_key: DEFAULT_TEMPLATE_KEY,
            })
          }
        >
          {busy === "/start"
            ? t("account.contract.startBusy")
            : t("account.contract.start")}
        </button>
        {openAwaitingSign?.contract_id ? (
          <>
            <button
              type="button"
              className="btn secondary"
              disabled={busy !== null}
              onClick={() =>
                postJson(
                  `/${String(openAwaitingSign.contract_id)}/signing-session`,
                )
              }
            >
              {busy ===
              `/${String(openAwaitingSign.contract_id)}/signing-session`
                ? t("account.contract.signingBusy")
                : t("account.contract.signingSession")}
            </button>
            <button
              type="button"
              className="btn secondary"
              disabled={busy !== null}
              onClick={() =>
                postJson(
                  `/${String(openAwaitingSign.contract_id)}/mock-complete-sign`,
                )
              }
            >
              {busy ===
              `/${String(openAwaitingSign.contract_id)}/mock-complete-sign`
                ? t("account.contract.mockBusy")
                : t("account.contract.mockComplete")}
            </button>
          </>
        ) : null}
        <button
          type="button"
          className="btn ghost"
          disabled={busy !== null}
          onClick={() => router.refresh()}
        >
          {t("account.contract.refresh")}
        </button>
      </div>

      {initialContracts.length === 0 ? (
        <p className="muted">{t("account.contract.emptyContracts")}</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("account.contract.thTemplate")}</th>
                <th>{t("account.contract.thStatus")}</th>
                <th>{t("account.contract.thUpdated")}</th>
                <th>{t("account.contract.thReview")}</th>
                <th>{t("account.contract.thMessage")}</th>
                <th>{t("account.contract.docsTitle")}</th>
              </tr>
            </thead>
            <tbody>
              {initialContracts.map((c) => {
                const cid = String(c.contract_id ?? "");
                return (
                  <tr key={cid}>
                    <td className="mono-small">
                      {String(c.template_key)} v{String(c.template_version)}
                    </td>
                    <td>{String(c.status)}</td>
                    <td className="mono-small">
                      {String(c.updated_ts ?? "—")}
                    </td>
                    <td>
                      {c.review_queue_status != null
                        ? String(c.review_queue_status)
                        : "—"}
                    </td>
                    <td>
                      {c.review_customer_message_public != null
                        ? String(c.review_customer_message_public)
                        : "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn link"
                        onClick={() => void toggleExpand(cid)}
                      >
                        {expanded === cid ? "−" : "+"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {expanded ? (
        <div className="panel nested" style={{ marginTop: "1rem" }}>
          <h4 className="account-section-title">
            {t("account.contract.docsTitle")}
          </h4>
          {(docsByContract[expanded] ?? []).length === 0 ? (
            <p className="muted small">{t("account.contract.noDocs")}</p>
          ) : (
            <ul className="news-list">
              {(docsByContract[expanded] ?? []).map((d) => {
                const did = String(d.document_id);
                const kind = String(d.document_kind);
                const href = gatewayContractsPath(
                  `/${expanded}/documents/${did}/download`,
                );
                const label =
                  kind === "signed_pdf"
                    ? t("account.contract.downloadSigned")
                    : t("account.contract.downloadDraft");
                return (
                  <li key={did}>
                    <a
                      href={href}
                      className="link"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {label}
                    </a>{" "}
                    <span className="mono-small muted">({kind})</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
