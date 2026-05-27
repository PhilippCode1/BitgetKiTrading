import { getCustomerPortalSummary } from "@/lib/customer-portal-summary";
import { TradingPageClient } from "./TradingPageClient";

export const dynamic = "force-dynamic";

export default async function CustomerPortalTradingPage() {
  const summary = await getCustomerPortalSummary();

  return (
    <TradingPageClient summary={summary} />
  );
}
