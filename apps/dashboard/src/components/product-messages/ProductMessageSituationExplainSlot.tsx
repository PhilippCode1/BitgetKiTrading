"use client";

import { SituationAiExplainPanel } from "@/components/diagnostics/SituationAiExplainPanel";
import type { ProductMessage } from "@/lib/product-messages/schema";
import { severityRank } from "@/lib/product-messages/schema";

type Props = Readonly<{
  message: ProductMessage;
  enabled?: boolean;
}>;

/**
 * Client-Insel: KI-/Kontext-Erklärung zu produktreifen Meldungen (ab „Hinweis“).
 */
export function ProductMessageSituationExplainSlot({
  message,
  enabled = true,
}: Props) {
  if (!enabled) return null;
  if (severityRank(message.severity) < severityRank("hint")) return null;
  return <SituationAiExplainPanel variant="product_message" message={message} />;
}
