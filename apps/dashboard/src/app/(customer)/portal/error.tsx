"use client";

import { AppErrorFallback } from "@/components/layout/AppErrorFallback";

export default function PortalErrorBoundary({
  error,
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  return (
    <AppErrorFallback
      error={error}
      reset={reset}
      showCustomerPortalLink
    />
  );
}
