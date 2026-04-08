/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { ConsoleFetchNotice } from "@/components/console/ConsoleFetchNotice";

jest.mock("@/components/console/ConsoleFetchNoticeActions", () => ({
  ConsoleFetchNoticeActions: () => (
    <div data-testid="mock-fetch-actions">actions</div>
  ),
}));

describe("ConsoleFetchNotice", () => {
  it("verkettet titlePrefix und title zu einer Zeile", () => {
    render(
      <ConsoleFetchNotice titlePrefix="Live-Terminal" title="Keine Daten" />,
    );
    expect(screen.getByText("Live-Terminal: Keine Daten")).toBeInTheDocument();
  });

  it("verkettet refreshHint und refreshExtra", () => {
    render(
      <ConsoleFetchNotice
        refreshHint="Seite neu laden."
        refreshExtra="Oder warten."
      />,
    );
    expect(
      screen.getByText("Seite neu laden. Oder warten."),
    ).toBeInTheDocument();
  });

  it("rendert Kinder und Diagnose-Block", () => {
    render(
      <ConsoleFetchNotice
        title="Hinweis"
        diagnosticSummaryLabel="Technik"
        technical="ERR_1"
        showTechnical
      >
        <ul data-testid="child-list">
          <li>eins</li>
        </ul>
      </ConsoleFetchNotice>,
    );
    expect(screen.getByTestId("child-list")).toBeInTheDocument();
    expect(screen.getByText("Technik")).toBeInTheDocument();
    expect(screen.getByText("ERR_1")).toBeInTheDocument();
  });

  it("bindet Schnellaktionen mit wrapActions ein", async () => {
    render(<ConsoleFetchNotice showStateActions wrapActions title="X" />);
    expect(await screen.findByTestId("mock-fetch-actions")).toBeInTheDocument();
    expect(
      document.querySelector(".console-fetch-notice-actions-wrap"),
    ).not.toBeNull();
  });
});
