"use client";

import { useEffect } from "react";

import { looksLikeRawServerPayloadString } from "@/lib/server-payload-text";

import "./globals.css";

const GLOBAL_USER_GENERIC =
  "Die Anwendung musste wegen einer technischen Störung anhalten. Bitte „Erneut versuchen“ — Details stehen nur in der vollen Shell, nicht in dieser Mindestansicht.";

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

  const raw = error.message?.trim() ?? "";
  const isRawApiBlob = raw && looksLikeRawServerPayloadString(raw, 20);
  const userLine = isRawApiBlob
    ? GLOBAL_USER_GENERIC
    : raw || "Die Anwendung konnte nicht gestartet werden.";

  return (
    <html lang="de">
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
          Schwerer Fehler
        </h1>
        <p style={{ opacity: 0.85, margin: "0 0 16px", maxWidth: 480 }}>
          {userLine}
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
          Erneut versuchen
        </button>
      </body>
    </html>
  );
}
