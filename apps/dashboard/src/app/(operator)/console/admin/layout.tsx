import type { ReactNode } from "react";

import { AdminHubSubnav } from "@/components/admin/AdminHubSubnav";
import { hasOperatorAdminAccess } from "@/lib/operator-session";

type Props = Readonly<{ children: ReactNode }>;

export default async function AdminSectionLayout({ children }: Props) {
  const ok = await hasOperatorAdminAccess();
  return (
    <div className="admin-hub">
      <div className="admin-hub__inner">
        {ok ? <AdminHubSubnav /> : null}
        {children}
      </div>
    </div>
  );
}
