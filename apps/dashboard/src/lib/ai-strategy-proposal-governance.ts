/**
 * Clientseitige Spiegelung der Promotions-Grenzen (Server bleibt maßgeblich).
 * Keine Orderfreigabe: nur UI-Vorprüfung.
 */

export type PromotionPrecheckResult = Readonly<{
  ok: boolean;
  code?: "HUMAN_ACK_REQUIRED" | "VALIDATION_REQUIRED";
}>;

export function precheckPromotionRequest(input: {
  lifecycleStatus: string;
  humanAcknowledged: boolean;
}): PromotionPrecheckResult {
  if (!input.humanAcknowledged) {
    return { ok: false, code: "HUMAN_ACK_REQUIRED" };
  }
  if (input.lifecycleStatus !== "validation_passed") {
    return { ok: false, code: "VALIDATION_REQUIRED" };
  }
  return { ok: true };
}
