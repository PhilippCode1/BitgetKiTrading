"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { mockLoginAvailable, portalAuthProvider } from "@/lib/auth/portal-auth-adapter";
import { sanitizeReturnTo } from "@/lib/return-to-safety";

import { loginAction, startOidcLoginAction } from "./actions";

type LoginRole = "customer" | "admin";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = sanitizeReturnTo(searchParams.get("returnTo"), "");
  const oauthError = searchParams.get("error");

  const provider = portalAuthProvider();
  const mockAllowed = mockLoginAvailable().ok;

  const [role, setRole] = useState<LoginRole>("customer");
  const [tenantId, setTenantId] = useState("tenant_demo_123");
  const [error, setError] = useState<string | null>(
    oauthError ? `Anmeldung fehlgeschlagen (${oauthError}).` : null,
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
      setError(result.error);
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
      setError(result.error);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler.");
    } finally {
      setBusy(false);
    }
  }

  if (provider === "oidc" && !mockAllowed) {
    return (
      <main className="welcome-gate">
        <div className="welcome-card panel mock-login-card">
          <h1>Anmeldung</h1>
          <p className="welcome-lead">
            {busy
              ? "Weiterleitung zum Identity Provider…"
              : "OIDC-Anmeldung wird vorbereitet."}
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
    <main className="welcome-gate">
      <div className="welcome-card panel mock-login-card">
        <div className="welcome-title-row">
          <h1>{mockAllowed ? "Mock-Login (Entwicklung)" : "Anmeldung"}</h1>
        </div>
        <p className="welcome-lead">
          {mockAllowed
            ? "Wähle eine Rolle und melde dich für eine Test-Session an."
            : "Melde dich über den Identity Provider an."}
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
              setError(result.error);
              setBusy(false);
            }}
          >
            {busy ? "Weiterleitung…" : "Mit Identity Provider anmelden"}
          </button>
        ) : null}

        {mockAllowed ? (
          <form onSubmit={handleSubmit} className="mock-login-form" noValidate>
            <fieldset className="mock-login-roles" disabled={busy}>
              <legend className="mock-login-roles__legend">Rolle</legend>
              <div className="mock-login-roles__row" role="radiogroup">
                <button
                  type="button"
                  role="radio"
                  aria-checked={role === "customer"}
                  className={`public-btn ${role === "customer" ? "primary" : "secondary"} mock-login-role-btn`}
                  onClick={() => setRole("customer")}
                >
                  Kunde
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={role === "admin"}
                  className={`public-btn ${role === "admin" ? "primary" : "secondary"} mock-login-role-btn`}
                  onClick={() => setRole("admin")}
                >
                  Admin
                </button>
              </div>
            </fieldset>

            {role === "customer" ? (
              <label className="mock-login-field" htmlFor="tenantId">
                <span className="mock-login-field__label">Mandanten-ID</span>
                <input
                  id="tenantId"
                  name="tenantId"
                  type="text"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  placeholder="tenant_demo_123"
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
                Als Admin erhältst du vollen Systemzugriff. Nur für lokale Diagnose.
              </p>
            )}

            <button
              type="submit"
              className="public-btn primary mock-login-submit"
              disabled={busy}
            >
              {busy ? "Anmeldung läuft…" : "Anmelden"}
            </button>
          </form>
        ) : null}
      </div>
    </main>
  );
}
