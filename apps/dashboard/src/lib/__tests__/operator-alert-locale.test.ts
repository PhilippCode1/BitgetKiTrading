import { localizeOperatorAlert } from "@/lib/operator-alert-locale";
import type { OperatorAlertView } from "@/lib/operator-alerts-view-model";

const sample: OperatorAlertView = {
  titel_de: "DE Titel",
  titel_en: "EN title",
  beschreibung_de: "DE body",
  beschreibung_en: "EN body",
  empfohlene_aktion_de: "DE act",
  empfohlene_aktion_en: "EN act",
  nächster_sicherer_schritt_de: "DE next",
  nächster_sicherer_schritt_en: "EN next",
  severity: "P1",
  live_blockiert: true,
  betroffene_komponente: "test",
  betroffene_assets: [],
  technische_details_redacted: "",
  zeitpunkt: "2026-01-01T00:00:00Z",
  korrelation_id: "id-1",
  aktiv: true,
};

describe("localizeOperatorAlert", () => {
  it("liefert EN-Felder fuer locale en", () => {
    const t = localizeOperatorAlert(sample, "en");
    expect(t.title).toBe("EN title");
    expect(t.description).toBe("EN body");
  });

  it("liefert DE-Felder fuer locale de", () => {
    const t = localizeOperatorAlert(sample, "de");
    expect(t.title).toBe("DE Titel");
    expect(t.description).toBe("DE body");
  });
});
