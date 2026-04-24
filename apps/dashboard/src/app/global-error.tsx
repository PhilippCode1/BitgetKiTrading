"use client";

import { useEffect } from "react";

import { DEFAULT_LOCALE } from "@/lib/i18n/config";
import { getMessagesForLocale } from "@/lib/i18n/load-messages";
import { buildTranslator } from "@/lib/i18n/resolve-message";

import "./globals.css";

const { messages, fallback } = getMessagesForLocale(DEFAULT_LOCALE);
const t = buildTranslator(DEFAULT_LOCALE, messages, fallback);

/**
 * Mindest-UI ohne App-Provider: ausschliesslich statische i18n-Texte — kein `error.message`,
 * kein JSON, kein Stacktrace (Fehler nur in der Konsole).
 */
export default function GlobalError({
  error,
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang={DEFAULT_LOCALE}>
      <body
        style={{
          margin: 0,
          padding: 24,
          fontFamily: "system-ui, sans-serif",
          background: "#0f0e0a",
          color: "#e8e4dc",
        }}
      >
        <h1 style={{ fontSize: "1.25rem", margin: "0 0 12px" }}>
          {t("ui.globalError.title")}
        </h1>
        <p style={{ opacity: 0.85, margin: "0 0 16px", maxWidth: 480 }}>
          {t("ui.globalError.body")}
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
          {t("ui.globalError.reload")}
        </button>
      </body>
    </html>
  );
}
