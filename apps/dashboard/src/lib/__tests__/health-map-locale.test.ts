import { buildHealthMapViewModel } from "@/lib/health-map-view-model";
import {
  healthMapBlockerReasons,
  localizeHealthMapComponent,
} from "@/lib/health-map-locale";

describe("healthMapBlockerReasons", () => {
  it("liefert EN-Blocker wenn locale en", () => {
    const model = buildHealthMapViewModel({ health: null, runtime: null });
    const en = healthMapBlockerReasons(model, "en");
    const de = healthMapBlockerReasons(model, "de");
    expect(en.length).toBe(de.length);
    if (en.length > 0) {
      expect(en[0]).not.toBe(de[0]);
    }
  });
});

describe("localizeHealthMapComponent", () => {
  it("nutzt EN-Felder fuer fehlergrund und naechsten Schritt", () => {
    const model = buildHealthMapViewModel({ health: null, runtime: null });
    const gateway = model.komponenten.find((c) => c.komponente === "API-Gateway");
    expect(gateway).toBeDefined();
    const de = localizeHealthMapComponent(gateway!, "de");
    const en = localizeHealthMapComponent(gateway!, "en");
    expect(de.errorReason).toContain("nicht erreichbar");
    expect(en.errorReason).toContain("unreachable");
    expect(en.nextStep).not.toBe(de.nextStep);
  });
});
