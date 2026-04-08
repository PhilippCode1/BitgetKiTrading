/** Einheitliche Fehlertexte für parallele Gateway-Fetches (Paper, Live-Broker, …). */
export function gatewayFetchErrorMessage(reason: unknown): string {
  if (reason instanceof Error) return reason.message;
  return String(reason);
}
