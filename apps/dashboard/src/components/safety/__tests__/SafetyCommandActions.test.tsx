/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { SafetyCommandActions } from "@/components/safety/SafetyCommandActions";

jest.mock("next/navigation", () => ({
  usePathname: () => "/console/safety-center",
  useRouter: () => ({
    refresh: jest.fn(),
    replace: jest.fn(),
    push: jest.fn(),
  }),
}));

describe("SafetyCommandActions", () => {
  it("zeigt lokalisierte Aktionszeilen", () => {
    render(
      <I18nProvider initialLocale="de">
        <SafetyCommandActions />
      </I18nProvider>,
    );
    expect(
      screen.getByRole("heading", { name: /Sicherheitsaktionen/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Live pausieren/i)).toBeInTheDocument();
    expect(screen.getByText(/Kill-Switch armieren/i)).toBeInTheDocument();
  });
});
