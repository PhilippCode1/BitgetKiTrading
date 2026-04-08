import type { Metadata } from "next";
import type { ReactNode } from "react";

import { FlowNavBar } from "@/components/layout/FlowNavBar";

/** Sprach-Gate ohne Marketing-Shell — nur Schritt 1. */
export const metadata: Metadata = {
  title: "Sprache / Language",
  robots: { index: false, follow: false },
};

export default async function WelcomeLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <>
      <FlowNavBar />
      {children}
    </>
  );
}
