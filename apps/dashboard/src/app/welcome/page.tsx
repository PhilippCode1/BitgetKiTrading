import { Suspense } from "react";

import { WelcomeLanguageClient } from "@/components/i18n/WelcomeLanguageClient";
import { PageLoadingSkeleton } from "@/components/layout/PageLoadingSkeleton";

export const dynamic = "force-dynamic";

export default function WelcomePage() {
  return (
    <Suspense
      fallback={
        <main className="welcome-gate">
          <div className="welcome-card panel">
            <PageLoadingSkeleton />
          </div>
        </main>
      }
    >
      <WelcomeLanguageClient />
    </Suspense>
  );
}
