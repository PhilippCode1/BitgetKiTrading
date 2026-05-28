import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { loginRouteEnabled } from "@/lib/auth/portal-auth-adapter";

type Props = Readonly<{ children: ReactNode }>;

/** Mock nur Dev/Test; OIDC-Login auch in Production erlaubt. */
export default function LoginLayout({ children }: Props) {
  if (!loginRouteEnabled()) {
    notFound();
  }
  return children;
}
