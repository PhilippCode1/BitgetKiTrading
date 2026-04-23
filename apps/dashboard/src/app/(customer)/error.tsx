"use client";

import { AppErrorFallback } from "@/components/layout/AppErrorFallback";

/**
 * Fehler in der Kunden-Route-Group: keine Konsole, Rückweg ins Portal.
 */
export default function CustomerRouteGroupError({
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
