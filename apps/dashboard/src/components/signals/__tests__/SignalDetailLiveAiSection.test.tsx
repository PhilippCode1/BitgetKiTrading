/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { SignalDetailLiveAiSection } from "@/components/signals/SignalDetailLiveAiSection";

describe("SignalDetailLiveAiSection", () => {
  it("zeigt Hinweis auf fehlende Ausfuehrungsbefugnis", () => {
    render(
      <SignalDetailLiveAiSection t={(k) => k}>
        <div>Inhalt</div>
      </SignalDetailLiveAiSection>,
    );
    expect(
      screen.getByText(/KI-Hinweis: keine Ausfuehrungsbefugnis/i),
    ).toBeInTheDocument();
  });
});
