import { redirect } from "next/navigation";

import { portalAccountPath } from "@/lib/console-paths";

export const dynamic = "force-dynamic";

/** Ehemaliger Pfad — Nav zeigt auf Vertrag & Abrechnung unter /portal/account/billing */
export default function CustomerContractRedirectPage() {
  redirect(portalAccountPath("billing"));
}
