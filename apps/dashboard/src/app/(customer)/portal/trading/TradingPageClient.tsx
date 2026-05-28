"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import type { CustomerPortalSummary } from "@/lib/customer-portal-summary";

type Props = Readonly<{
  summary: CustomerPortalSummary;
}>;

type GoLiveErrorCode =
  | "MISSING_API_KEYS"
  | "INVALID_API_KEYS"
  | "CONTRACT_NOT_SIGNED"
  | "INSUFFICIENT_BALANCE"
  | "DEMO_MODE_ACTIVE"
  | "ACCOUNT_SUSPENDED"
  | "ACCOUNT_PAUSED"
  | "EMAIL_NOT_VERIFIED"
  | "STEP_UP_REQUIRED"
  | "STEP_UP_INVALID"
  | "PORTAL_SESSION_REQUIRED"
  | "TENANT_ID_REQUIRED"
  | "UNKNOWN_ERROR";

type GoLivePreflight = {
  step_up_required?: boolean;
  ready?: boolean;
  blockers?: string[];
  demo_mode_active?: boolean;
};

type GoLiveDetail = {
  error?: string;
  message?: string;
  min?: string;
  current?: string;
};

type GoLiveResponse =
  | {
      status: "ok";
      live_trading_allowed: boolean;
      shadow_only_until?: string | null;
      cooldown_sec?: number;
    }
  | { detail?: GoLiveDetail };

function parseErrorCode(raw: string | undefined): GoLiveErrorCode {
  const allowed: readonly GoLiveErrorCode[] = [
    "MISSING_API_KEYS",
    "INVALID_API_KEYS",
    "CONTRACT_NOT_SIGNED",
    "INSUFFICIENT_BALANCE",
    "DEMO_MODE_ACTIVE",
    "ACCOUNT_SUSPENDED",
    "ACCOUNT_PAUSED",
    "EMAIL_NOT_VERIFIED",
    "STEP_UP_REQUIRED",
    "STEP_UP_INVALID",
    "PORTAL_SESSION_REQUIRED",
    "TENANT_ID_REQUIRED",
  ];
  if (raw && (allowed as readonly string[]).includes(raw)) {
    return raw as GoLiveErrorCode;
  }
  return "UNKNOWN_ERROR";
}

function settingsRouteForErrorCode(code: GoLiveErrorCode): string | null {
  switch (code) {
    case "MISSING_API_KEYS":
    case "INVALID_API_KEYS":
      return "/portal/exchange";
    case "CONTRACT_NOT_SIGNED":
      return "/portal/contract";
    case "INSUFFICIENT_BALANCE":
      return "/portal/account/billing";
    case "EMAIL_NOT_VERIFIED":
      return "/portal/account";
    default:
      return null;
  }
}

export function TradingPageClient({ summary }: Props) {
  const { t } = useI18n();
  const router = useRouter();

  const gates = summary.commerceLifecycle?.body?.gatesPreview;
  const isLive = gates?.admin_live_trading_granted === true;

  const [modalOpen, setModalOpen] = useState(false);
  const [acceptedCheckbox, setAcceptedCheckbox] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<GoLiveErrorCode | null>(null);
  const [success, setSuccess] = useState(false);
  const [shadowOnlyUntil, setShadowOnlyUntil] = useState<string | null>(null);
  const [stepUpRequired, setStepUpRequired] = useState(false);
  const [stepUpCode, setStepUpCode] = useState("");
  const [preflightBlockers, setPreflightBlockers] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/dashboard/commerce/customer/live-execution/preflight", {
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) return;
        const data = (await res.json()) as GoLivePreflight;
        if (!cancelled) {
          setStepUpRequired(data.step_up_required === true);
          setPreflightBlockers(Array.isArray(data.blockers) ? data.blockers : []);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  function preflightBlockerMessage(code: string): string {
    switch (code) {
      case "MISSING_API_KEYS":
        return t("customerPortal.tradingPage.errorMissingKeys");
      case "CONTRACT_NOT_SIGNED":
        return t("customerPortal.tradingPage.errorContractNotSigned");
      case "INSUFFICIENT_BALANCE":
        return t("customerPortal.tradingPage.errorInsufficientBalance", { min: "50" });
      case "EMAIL_NOT_VERIFIED":
        return t("customerPortal.tradingPage.errorEmailNotVerified");
      case "DEMO_MODE_ACTIVE":
        return t("customerPortal.tradingPage.errorDemoMode");
      case "ACCOUNT_PAUSED":
        return t("customerPortal.tradingPage.errorAccountPaused");
      case "ACCOUNT_SUSPENDED":
        return t("customerPortal.tradingPage.errorAccountSuspended");
      default:
        return code;
    }
  }

  function resolveErrorMessage(
    code: GoLiveErrorCode,
    detail: GoLiveDetail | undefined,
  ): string {
    switch (code) {
      case "MISSING_API_KEYS":
        return t("customerPortal.tradingPage.errorMissingKeys");
      case "INVALID_API_KEYS":
        return t("customerPortal.tradingPage.errorInvalidKeys");
      case "CONTRACT_NOT_SIGNED":
        return t("customerPortal.tradingPage.errorContractNotSigned");
      case "INSUFFICIENT_BALANCE":
        return t("customerPortal.tradingPage.errorInsufficientBalance", {
          min: detail?.min ?? "50",
        });
      case "EMAIL_NOT_VERIFIED":
        return t("customerPortal.tradingPage.errorEmailNotVerified");
      case "STEP_UP_REQUIRED":
      case "STEP_UP_INVALID":
        return t("customerPortal.tradingPage.errorStepUpInvalid");
      default:
        return (
          detail?.message ??
          t("errors.fallbackMessage", {})
        );
    }
  }

  async function handleActivateLive() {
    setLoading(true);
    setError(null);
    setErrorCode(null);

    try {
      const res = await fetch(
        "/api/dashboard/commerce/customer/live-execution/enable",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({
            step_up_code: stepUpCode.trim() || null,
          }),
        },
      );

      let data: GoLiveResponse | Record<string, unknown> = {};
      try {
        data = (await res.json()) as GoLiveResponse;
      } catch {
        // body might be empty / non-json
      }

      if (!res.ok) {
        const raw = data as Record<string, unknown>;
        const detail = (
          typeof raw.detail === "object" && raw.detail !== null
            ? raw.detail
            : raw
        ) as GoLiveDetail | undefined;
        const code = parseErrorCode(detail?.error);
        setErrorCode(code);
        setError(resolveErrorMessage(code, detail));
        setModalOpen(false);
        return;
      }

      setSuccess(true);
      if ("shadow_only_until" in data && data.shadow_only_until) {
        setShadowOnlyUntil(String(data.shadow_only_until));
      } else {
        setShadowOnlyUntil(null);
      }
      setModalOpen(false);
      router.refresh();
    } catch (err) {
      console.error("[trading] enable-live failed:", err);
      setError(t("errors.fallbackMessage", {}));
      setModalOpen(false);
    } finally {
      setLoading(false);
    }
  }

  const errorSettingsRoute = errorCode ? settingsRouteForErrorCode(errorCode) : null;

  return (
    <div className="panel" data-e2e="customer-portal-trading">
      <h1>{t("customerPortal.tradingPage.title")}</h1>
      <p className="muted">{t("customerPortal.tradingPage.lead")}</p>

      <section
        className={`execution-mode-card ${isLive ? "is-live" : ""}`}
        data-e2e="execution-mode-card"
      >
        <h2 className="execution-mode-card__title">
          {t("customerPortal.tradingPage.executionModeTitle")}
        </h2>
        <p className="execution-mode-card__mode">
          <strong>{t("customerPortal.tradingPage.modeLabel")}</strong>
          <span className={isLive ? "is-live-text" : ""}>
            {isLive
              ? t("customerPortal.tradingPage.modeLive")
              : t("customerPortal.tradingPage.modePaper")}
          </span>
        </p>

        {!isLive && !success ? (
          <>
            {preflightBlockers.length > 0 ? (
              <div
                className="activation-preflight-blockers"
                role="status"
                data-e2e="go-live-preflight-blockers"
              >
                <p className="muted">{t("customerPortal.tradingPage.preflightBlockersLead")}</p>
                <ul>
                  {preflightBlockers.map((code) => (
                    <li key={code}>{preflightBlockerMessage(code)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <button
              type="button"
              className="public-btn primary execution-mode-card__enable"
              data-e2e="enable-live-btn"
              disabled={preflightBlockers.length > 0}
              onClick={() => {
                setAcceptedCheckbox(false);
                setStepUpCode("");
                setError(null);
                setErrorCode(null);
                setModalOpen(true);
              }}
            >
              {t("customerPortal.tradingPage.enableLiveBtn")}
            </button>
          </>
        ) : null}
      </section>

      {success ? (
        <section className="activation-success-banner" role="status" data-e2e="go-live-success">
          <h3>{t("customerPortal.tradingPage.successTitle")}</h3>
          <p className="muted">
            {shadowOnlyUntil
              ? t("customerPortal.tradingPage.successShadowMsg", {
                  until: new Date(shadowOnlyUntil).toLocaleString(),
                })
              : t("customerPortal.tradingPage.successMsg")}
          </p>
        </section>
      ) : null}

      {error ? (
        <section className="activation-error-banner" role="alert">
          <p className="activation-error-banner__message">{error}</p>
          {errorSettingsRoute ? (
            <div className="activation-error-banner__actions">
              <button
                type="button"
                className="public-btn secondary"
                onClick={() => router.push(errorSettingsRoute)}
              >
                {t("customerPortal.tradingPage.goToSettingsBtn")}
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      {modalOpen ? (
        <div className="modal-backdrop" role="presentation">
          <div
            className="panel modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="go-live-modal-title"
          >
            <h3 id="go-live-modal-title">
              {t("customerPortal.tradingPage.modalTitle")}
            </h3>
            <p className="muted modal-panel__warning">
              {t("customerPortal.tradingPage.modalWarning")}
            </p>

            <label className="modal-panel__check">
              <input
                type="checkbox"
                checked={acceptedCheckbox}
                onChange={(e) => setAcceptedCheckbox(e.target.checked)}
                data-e2e="modal-confirm-checkbox"
              />
              <span className="muted">
                {t("customerPortal.tradingPage.modalUnderstandCheckbox")}
              </span>
            </label>

            {stepUpRequired ? (
              <label className="mock-login-field modal-panel__step-up" htmlFor="go-live-step-up">
                <span className="mock-login-field__label">
                  {t("customerPortal.tradingPage.stepUpLabel")}
                </span>
                <input
                  id="go-live-step-up"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={32}
                  value={stepUpCode}
                  onChange={(e) => setStepUpCode(e.target.value)}
                  data-e2e="modal-step-up-input"
                  disabled={loading}
                  className="mock-login-input"
                />
              </label>
            ) : null}

            <div className="btn-row modal-panel__actions">
              <button
                type="button"
                className="public-btn secondary"
                onClick={() => setModalOpen(false)}
                disabled={loading}
              >
                {t("customerPortal.tradingPage.modalCancelBtn")}
              </button>
              <button
                type="button"
                className="public-btn primary modal-panel__confirm"
                disabled={
                  !acceptedCheckbox ||
                  loading ||
                  (stepUpRequired && stepUpCode.trim().length < 6)
                }
                onClick={handleActivateLive}
                data-e2e="modal-confirm-btn"
              >
                {loading
                  ? t("customerPortal.tradingPage.modalConfirmLoading")
                  : t("customerPortal.tradingPage.modalConfirmBtn")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <p className="muted">{t("customerPortal.tradingPage.noExecution")}</p>
    </div>
  );
}
