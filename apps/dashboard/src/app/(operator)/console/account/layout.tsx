import { Suspense, type ReactNode } from "react";

import { AccountSubnav } from "@/components/account/AccountSubnav";
import { CustomerAreaShell } from "@/components/account/CustomerAreaShell";
import { CustomerAreaSkeleton } from "@/components/account/CustomerAreaSkeleton";

type Props = Readonly<{ children: ReactNode }>;

export default function AccountLayout({ children }: Props) {
  return (
    <CustomerAreaShell>
      <AccountSubnav />
      <Suspense fallback={<CustomerAreaSkeleton />}>{children}</Suspense>
    </CustomerAreaShell>
  );
}
