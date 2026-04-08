import { mirrorLocalePreferenceToServer } from "../best-effort-fetch";

describe("mirrorLocalePreferenceToServer", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("protokolliert Warnung bei HTTP-Fehler ohne zu werfen", async () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
    } as Response);

    await mirrorLocalePreferenceToServer("de");

    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining(
        "[dashboard] preferences/locale mirror: HTTP 503",
      ),
    );
  });

  it("protokolliert Warnung bei Netzwerkfehler ohne zu werfen", async () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    global.fetch = jest.fn().mockRejectedValue(new Error("network down"));

    await mirrorLocalePreferenceToServer("en");

    expect(warn).toHaveBeenCalledWith(expect.stringContaining("network down"));
  });
});
