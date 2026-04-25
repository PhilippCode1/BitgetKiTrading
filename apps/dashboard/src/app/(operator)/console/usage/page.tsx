import { consolePath } from "@/lib/console-paths";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function UsagePage() {
  redirect(consolePath("reports"));
}
