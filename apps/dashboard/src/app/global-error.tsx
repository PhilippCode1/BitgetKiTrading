"use client";

import { useEffect, useMemo } from "react";

import "./globals.css";

const COPY = {
  de: {
    title: "Schwerer Fehler",
    body: "Die Anwendung musste anhalten. Bitte „Erneut versuchen“.",
    reload: "Erneut versuchen",
  },
  en: {
    title: "Severe error",
    body: "The application had to stop. Please use “Try again”.",
    reload: "Try again",
  },
} as const;

function readLocale(): keyof typeof COPY {
  if (typeof document === "undefined") return "de";
  const m = document.cookie.match(/(?:^|;\s*)bitget_dashboard_locale=(\w+)/);
  return m?.[1] === "en" ? "en" : "de";
}

/**
 * Mindest-UI ohne App-Provider — Texte aus festem DE/EN-Katalog (Locale-Cookie).
 */
export default function GlobalError({
  error,
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  const locale = useMemo(() => readLocale(), []);
  const copy = COPY[locale];

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang={locale}>
      <body
        style={{
          margin: 0,
          padding: 24,
          fontFamily: "system-ui, sans-serif",
          background: "#0f0e0a",
          color: "#e8e4dc",
        }}
      >
        <div role="alert">
          <h1 style={{ fontSize: "1.25rem", margin: "0 0 12px" }}>
            {copy.title}
          </h1>
          <p style={{ opacity: 0.85, margin: "0 0 16px", maxWidth: 480 }}>
            {copy.body}
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "10px 18px",
              borderRadius: 8,
              border: "1px solid #5c5340",
              background: "#1a1812",
              color: "#d4af37",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {copy.reload}
          </button>
        </div>
      </body>
    </html>
  );
}
