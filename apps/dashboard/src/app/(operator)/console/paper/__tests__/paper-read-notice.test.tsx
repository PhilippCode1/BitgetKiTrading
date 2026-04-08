/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";

import { GatewayReadNotice } from "@/components/console/GatewayReadNotice";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { buildTranslator } from "@/lib/i18n/resolve-message";
import type { MessageTree } from "@/lib/i18n/resolve-message";
import de from "@/messages/de.json";
import en from "@/messages/en.json";

import { PaperReadNotice } from "../paper-read-notice";

const tDe = buildTranslator("de", de as MessageTree, en as MessageTree);

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/paper",
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

function wrap(ui: ReactElement) {
  return render(<I18nProvider initialLocale="de">{ui}</I18nProvider>);
}

describe("PaperReadNotice", () => {
  it("ist derselbe Export wie GatewayReadNotice", () => {
    expect(PaperReadNotice).toBe(GatewayReadNotice);
  });
});

describe("GatewayReadNotice", () => {
  it("zeigt bei degraded die Nachricht und next_step als Produktmeldung", () => {
    wrap(
      <GatewayReadNotice
        t={tDe}
        payload={{
          status: "degraded",
          message: "Kurz nicht ladbar.",
          empty_state: true,
          degradation_reason: "x",
          next_step: "DB prüfen",
        }}
      />,
    );
    expect(
      screen.getByRole("heading", { level: 3, name: "Kurz nicht ladbar." }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Empfohlener Schritt vom System: DB prüfen"),
    ).toBeInTheDocument();
  });

  it("nutzt Generic-Text wenn degraded ohne message", () => {
    wrap(
      <GatewayReadNotice
        t={tDe}
        payload={{
          status: "degraded",
          message: null,
          empty_state: true,
          degradation_reason: null,
          next_step: null,
        }}
      />,
    );
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Daten vorübergehend eingeschränkt.",
      }),
    ).toBeInTheDocument();
  });
});
