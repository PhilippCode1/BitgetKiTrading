import type { TranslateFn } from "@/components/i18n/I18nProvider";
import { ProductMessageCard } from "@/components/product-messages/ProductMessageCard";
import type { GatewayReadEnvelope } from "@/lib/types";
import { buildProductMessageFromGatewayEnvelope } from "@/lib/product-messages";

type Props = Readonly<{
  payload: GatewayReadEnvelope;
  t: TranslateFn;
  /** RFC: ?diagnostic=1 — technische Klappe */
  diagnostic?: boolean;
}>;

/**
 * Gateway-Lesenvelope mit produktreifem Meldungsschema (keine generischen Einzeiler).
 */
export function GatewayReadNotice({
  payload,
  t,
  diagnostic = false,
}: Props) {
  const message = buildProductMessageFromGatewayEnvelope(payload, t);
  if (!message) return null;
  return (
    <ProductMessageCard
      message={message}
      showTechnical={diagnostic}
      t={t}
      className="gateway-read-notice"
    />
  );
}
