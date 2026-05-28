import { buildSystemDiagnosticsViewModel } from "@/lib/system-diagnostics-view-model";
import {
  localizeDiagnosticsEmptyLine,
  localizeDiagnosticsOverallStatus,
  localizeDiagnosticsReasonKey,
  localizeStaleCheckDetail,
  localizeWireStatus,
} from "@/lib/system-diagnostics-locale";
import { buildTranslator } from "@/lib/i18n/resolve-message";
import { getMessagesForLocale } from "@/lib/i18n/load-messages";

function deT() {
  const { messages, fallback } = getMessagesForLocale("de");
  return buildTranslator("de", messages, fallback);
}

function enT() {
  const { messages, fallback } = getMessagesForLocale("en");
  return buildTranslator("en", messages, fallback);
}

describe("system-diagnostics-locale", () => {
  it("lokalisiert Gesamtstatus und Stale-Details", () => {
    const model = buildSystemDiagnosticsViewModel({
      health: null,
      runtime: null,
      liveState: null,
      openAlerts: [],
      healthEndpointWired: false,
    });
    const tDe = deT();
    const tEn = enT();
    expect(localizeDiagnosticsOverallStatus(model.overallStatus, tDe)).toBe(
      "Blockiert",
    );
    expect(localizeDiagnosticsOverallStatus(model.overallStatus, tEn)).toBe(
      "Blocked",
    );
    const candles = model.staleChecks.find((c) => c.key === "candles");
    expect(candles).toBeDefined();
    expect(localizeStaleCheckDetail(candles!, tDe)).toMatch(/Kerzen/);
    expect(localizeStaleCheckDetail(candles!, tEn)).toMatch(/Candles/);
    expect(
      localizeDiagnosticsReasonKey("healthEndpointUnwired", tEn),
    ).toMatch(/not wired/i);
    expect(localizeWireStatus("__alerts_open__:3", tEn)).toMatch(/open: 3/);
    expect(
      localizeDiagnosticsEmptyLine("__service_ok__:api-gateway", tEn),
    ).toMatch(/api-gateway.*last check ok/i);
  });
});
