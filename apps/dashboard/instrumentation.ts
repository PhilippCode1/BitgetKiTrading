export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { assertDashboardRuntimeEnvOrThrow } =
      await import("@/lib/runtime-env-gate");
    assertDashboardRuntimeEnvOrThrow();
  }
}
