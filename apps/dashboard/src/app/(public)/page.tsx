import { redirect } from "next/navigation";

import { CONSOLE_BASE } from "@/lib/console-paths";

export const dynamic = "force-dynamic";

export default async function ProductLandingPage() {
  redirect(CONSOLE_BASE);
}
