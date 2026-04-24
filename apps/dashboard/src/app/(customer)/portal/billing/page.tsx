import { redirect } from "next/navigation";

import { portalAccountPath } from "@/lib/console-paths";

export const dynamic = "force-dynamic";

/** Ehemaliger Pfad — siehe /portal/account/billing */
export default function CustomerBillingRedirectPage() {
  redirect(portalAccountPath("billing"));
}
