const path = require("path");

const isProdBuild = process.env.NODE_ENV === "production";
const apiBaseRaw = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
if (isProdBuild && !apiBaseRaw) {
  console.warn(
    "[dashboard next.config] Production-Build ohne NEXT_PUBLIC_API_BASE_URL — fuer Staging/Produktion setzen (Browser-API + CSP connect-src).",
  );
}
const devFallbackApi = "http://127.0.0.1:8000";
const apiBase = (apiBaseRaw || (!isProdBuild ? devFallbackApi : "")).replace(
  /\/$/,
  "",
);

let apiOrigin = "";
try {
  if (apiBase) {
    apiOrigin = new URL(apiBase).origin;
  }
} catch {
  apiOrigin = "";
}
if (!apiOrigin && !isProdBuild) {
  try {
    apiOrigin = new URL(devFallbackApi).origin;
  } catch {
    apiOrigin = "";
  }
}

const wsRaw = (process.env.NEXT_PUBLIC_WS_BASE_URL || "").trim();
let wsOrigin = "";
if (wsRaw) {
  try {
    wsOrigin = new URL(wsRaw).origin;
  } catch {
    wsOrigin = "";
  }
} else if (apiBase) {
  try {
    const u = new URL(apiBase);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    wsOrigin = u.origin;
  } catch {
    wsOrigin = "";
  }
}

/** Dev: breites connect-src fuer lokale Ports. Prod: nur konfigurierte API-/WS-Origin (keine localhost-Wildcards). */
const connectSrc = isProdBuild
  ? ["'self'", apiOrigin, wsOrigin].filter(Boolean).join(" ") || "'self'"
  : `'self' ${apiOrigin || devFallbackApi} ws: wss: http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:*`;

/** @type {import('next').NextConfig} */
const nextConfig = {
  /** Repo-Root: damit `pnpm dev` / Turbo aus apps/dashboard die gleiche .env.local wie Docker/Compose nutzt */
  envDir: path.join(__dirname, "../.."),
  reactStrictMode: true,
  async redirects() {
    const legacy = [
      "/ops",
      "/terminal",
      "/signals",
      "/live-broker",
      "/health",
      "/learning",
      "/paper",
      "/strategies",
      "/news",
      "/market-universe",
      "/admin",
    ];
    const nested = ["signals", "strategies", "news", "live-broker"];
    return [
      ...legacy.map((src) => ({
        source: src,
        destination: `/console${src}`,
        permanent: false,
      })),
      ...nested.map((p) => ({
        source: `/${p}/:path+`,
        destination: `/console/${p}/:path+`,
        permanent: false,
      })),
    ];
  },
  distDir: process.env.NEXT_DIST_DIR || "build",
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../.."),
  poweredByHeader: false,
  async headers() {
    const csp = [
      "default-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'self'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      `connect-src ${connectSrc}`,
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
