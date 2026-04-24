import { buildProductMessageFromFetchError } from "@/lib/product-messages";
import { apiFetchErrorFromHttp } from "@/lib/api-fetch-errors";
import { classifyFetchError } from "@/lib/user-facing-fetch-error";
import { DEFAULT_LOCALE } from "@/lib/i18n/config";
import { getMessagesForLocale } from "@/lib/i18n/load-messages";
import { buildTranslator } from "@/lib/i18n/resolve-message";

const { messages, fallback } = getMessagesForLocale(DEFAULT_LOCALE);
const t = buildTranslator(DEFAULT_LOCALE, messages, fallback);

function bffBody503AuthMissing(detail: string): string {
  return JSON.stringify({
    detail,
    code: "DASHBOARD_GATEWAY_AUTH_MISSING",
    layer: "dashboard-bff",
  });
}

describe("Gateway-Fehlercodes + Produktmeldung", () => {
  it("503 + DASHBOARD_GATEWAY_AUTH_MISSING wird als Konfiguration klassifiziert", () => {
    const err = apiFetchErrorFromHttp({
      path: "/v1/system/health",
      bffPath: "/api/dashboard/gateway/v1/system/health",
      status: 503,
      bodyText: bffBody503AuthMissing("Authorization header missing for dashboard BFF."),
    });
    expect(err.kind).toBe("config");
    expect(classifyFetchError(err)).toBe("configuration");
  });

  it("429 + RATE_LIMIT_EXCEEDED wird als rate_limited erkannt", () => {
    const err = apiFetchErrorFromHttp({
      path: "/v1/signals/recent",
      bffPath: "/api/dashboard/gateway/v1/signals/recent",
      status: 429,
      bodyText: JSON.stringify({ code: "RATE_LIMIT_EXCEEDED" }),
    });
    expect(err.kind).toBe("rate_limit");
    expect(classifyFetchError(err)).toBe("rate_limited");
  });

  it("ProductMessageCard-Text: kein Roh-JSON im sichtbaren Titel/Fliesstext", () => {
    const err = apiFetchErrorFromHttp({
      path: "/v1/paper/metrics/summary",
      bffPath: "/api/dashboard/gateway/v1/paper/metrics/summary",
      status: 503,
      bodyText: bffBody503AuthMissing('{"weird":true}'),
    });
    const pm = buildProductMessageFromFetchError(err, t);
    expect(pm.headline).not.toMatch(/^\s*\[/);
    expect(pm.headline).not.toMatch(/\{"/);
    expect(pm.summary).not.toMatch(/\{"/);
    expect(t("productMessage.fetch.configuration.headline")).toContain("Konfiguration");
    expect(pm.headline).toBe(t("productMessage.fetch.configuration.headline"));
  });
});
