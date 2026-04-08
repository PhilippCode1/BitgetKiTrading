/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { ConsolePartialLoadNotice } from "@/components/console/ConsolePartialLoadNotice";
import { ConsoleSurfaceNotice } from "@/components/console/ConsoleSurfaceNotice";

jest.mock("@/components/console/ConsoleFetchNoticeActions", () => ({
  ConsoleFetchNoticeActions: () => (
    <div data-testid="mock-fetch-actions">actions</div>
  ),
}));

const t = (key: string) => key;

describe("ConsoleSurfaceNotice", () => {
  it("setzt Titel und optionalen API-Body", () => {
    render(
      <ConsoleSurfaceNotice
        t={t}
        titleKey="ui.surfaceState.degraded.title"
        body="Server sagt: eingeschraenkt"
        showStateActions
      />,
    );
    expect(
      screen.getByText("ui.surfaceState.degraded.title"),
    ).toBeInTheDocument();
    expect(screen.getByText("Server sagt: eingeschraenkt")).toBeInTheDocument();
  });

  it("bindet Schnellaktionen", async () => {
    render(
      <ConsoleSurfaceNotice t={t} titleKey="x" bodyKey="y" showStateActions />,
    );
    expect(await screen.findByTestId("mock-fetch-actions")).toBeInTheDocument();
  });
});

describe("ConsolePartialLoadNotice", () => {
  it("rendert nichts ohne Zeilen", () => {
    const { container } = render(
      <ConsolePartialLoadNotice
        t={t}
        titleKey="a"
        bodyKey="b"
        lines={[]}
        diagnostic={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("listet Sektionsfehler und Diagnose-Block", () => {
    render(
      <ConsolePartialLoadNotice
        t={t}
        titleKey="pages.paper.partialLoadTitle"
        bodyKey="pages.paper.partialLoadBody"
        lines={["A: fehlgeschlagen"]}
        diagnostic
      />,
    );
    expect(
      screen.getByText("pages.paper.partialLoadTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("A: fehlgeschlagen").length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("ui.diagnostic.summary")).toBeInTheDocument();
  });
});
