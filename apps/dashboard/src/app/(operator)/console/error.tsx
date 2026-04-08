"use client";

import { AppErrorFallback } from "@/components/layout/AppErrorFallback";

export default function ConsoleErrorBoundary({
  error,
  reset,
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  return <AppErrorFallback error={error} reset={reset} />;
}
