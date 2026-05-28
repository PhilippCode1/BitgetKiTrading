"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";
import { mockLoginAvailable, portalAuthProvider } from "@/lib/auth/portal-auth-adapter";
import { loginErrorMessage } from "@/lib/login-error-message";
import { sanitizeReturnTo } from "@/lib/return-to-safety";

import { loginAction, startOidcLoginAction } from "./actions";

type LoginRole = "customer" | "admin";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useI18n();
  const returnTo = sanitizeReturnTo(searchParams.get("returnTo"), "");
  const oauthError = searchParams.get("error");

  const provider = portalAuthProvider();
  const mockAllowed = mockLoginAvailable().ok;

  const [role, setRole] = useState<LoginRole>("customer");
  const [tenantId, setTenantId] = useState("tenant_demo_123");
  const [error, setError] = useState<string | null>(
    oauthError
      ? t("public.login.oauthFailed", { code: oauthError })
      : null,
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (provider !== "oidc" || mockAllowed) return;
    let cancelled = false;
    (async () => {
      setBusy(true);
      const result = await startOidcLoginAction(returnTo);
      if (cancelled) return;
      if (result.success) {
        window.location.href = result.redirect;
        return;
      }
      setError(loginErrorMessage(t, result.errorCode));
      setBusy(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [provider, mockAllowed, returnTo]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("role", role);
      formData.append("tenantId", role === "customer" ? tenantId : "default");
      const result = await loginAction(formData);
      if (result.success) {
        const target = returnTo || result.redirect;
        router.push(target);
        router.refresh();
        return;
      }
      setError(loginErrorMessage(t, result.errorCode));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("public.login.unknownError"),
      );
    } finally {
      setBusy(false);
    }
  }

  if (provider === "oidc" && !mockAllowed) {
    return (
    <main className="welcome-gate" id="dash-main-content">
      <a href="#dash-main-content" className="skip-to-main">
        {t("ui.skipToMain")}
      </a>
      <div className="welcome-card panel mock-login-card">
        <h1>{t("public.login.title")}</h1>
          <p className="welcome-lead">
            {busy
              ? t("public.login.oidcRedirecting")
              : t("public.login.oidcPreparing")}
          </p>
          {error ? (
            <p className="msg-err mock-login-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </main>
    );
  }

  return (
    <main className="welcome-gate" id="dash-main-content">
      <a href="#dash-main-content" className="skip-to-main">
        {t("ui.skipToMain")}
      </a>
      <div className="welcome-card panel mock-login-card">
        <div className="welcome-title-row">
          <h1>
            {mockAllowed
              ? t("public.login.titleMock")
              : t("public.login.title")}
          </h1>
        </div>
        <p className="welcome-lead">
          {mockAllowed
            ? t("public.login.leadMock")
            : t("public.login.leadOidc")}
        </p>

        {error ? (
          <p className="msg-err mock-login-error" role="alert">
            {error}
          </p>
        ) : null}

        {provider === "oidc" ? (
          <button
            type="button"
            className="public-btn primary mock-login-submit"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              const result = await startOidcLoginAction(returnTo);
              if (result.success) {
                window.location.href = result.redirect;
                return;
              }
              setError(loginErrorMessage(t, result.errorCode));
              setBusy(false);
            }}
          >
            {busy
              ? t("public.login.redirectBusy")
              : t("public.login.oidcButton")}
          </button>
        ) : null}

        {mockAllowed ? (
          <form onSubmit={handleSubmit} className="mock-login-form" noValidate>
            <fieldset className="mock-login-roles" disabled={busy}>
              <legend className="mock-login-roles__legend">
                {t("public.login.roleLegend")}
              </legend>
              <div className="mock-login-roles__row" role="radiogroup">
                <button
                  type="button"
                  role="radio"
                  aria-checked={role === "customer"}
                  className={`public-btn ${role === "customer" ? "primary" : "secondary"} mock-login-role-btn`}
                  onClick={() => setRole("customer")}
                >
                  {t("public.login.roleCustomer")}
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={role === "admin"}
                  className={`public-btn ${role === "admin" ? "primary" : "secondary"} mock-login-role-btn`}
                  onClick={() => setRole("admin")}
                >
                  {t("public.login.roleAdmin")}
                </button>
              </div>
            </fieldset>

            {role === "customer" ? (
              <label className="mock-login-field" htmlFor="tenantId">
                <span className="mock-login-field__label">
                  {t("public.login.tenantLabel")}
                </span>
                <input
                  id="tenantId"
                  name="tenantId"
                  type="text"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  placeholder={t("public.login.tenantPlaceholder")}
                  disabled={busy}
                  required
                  autoComplete="off"
                  pattern="[A-Za-z0-9_-]{3,64}"
                  title="3–64 Zeichen, nur Buchstaben, Ziffern, _ oder -"
                  className="mock-login-input"
                />
              </label>
            ) : (
              <p className="mock-login-admin-note" role="note">
                {t("public.login.adminNote")}
              </p>
            )}

            <button
              type="submit"
              className="public-btn primary mock-login-submit"
              disabled={busy}
            >
              {busy
                ? t("public.login.submitBusy")
                : t("public.login.submit")}
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
