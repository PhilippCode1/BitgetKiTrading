import type { ReactNode } from "react";

type Props = Readonly<{ children: ReactNode }>;

export function CustomerAreaShell({ children }: Props) {
  return (
    <div className="customer-area">
      <div className="customer-area__inner">{children}</div>
    </div>
  );
}
