"use client";

import { useEffect } from "react";

import "./globals.css";

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
          {error.message?.trim() ||
            "Die Anwendung konnte nicht gestartet werden."}
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
