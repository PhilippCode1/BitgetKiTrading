import { Suspense } from "react";

import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { PageLoadingSkeleton } from "@/components/layout/PageLoadingSkeleton";

export const dynamic = "force-dynamic";

export default function OnboardingPage() {
  return (
    <Suspense
      fallback={
        <main className="onboarding-main">
          <div className="onboarding-card panel">
            <PageLoadingSkeleton />
          </div>
        </main>
      }
    >
      <OnboardingWizard />
    </Suspense>
  );
}
