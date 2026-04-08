import Link from "next/link";
import type { ComponentProps } from "react";

type Props = Omit<ComponentProps<typeof Link>, "className"> & {
  className?: string;
};

/**
 * Sekundärlink in Pill-Form (Toolbar, Status-Leisten) — einheitlich mit Live-Terminal.
 */
export function StatusPillLink({ className = "", style, ...rest }: Props) {
  return (
    <Link
      {...rest}
      className={`status-pill${className ? ` ${className}` : ""}`}
      style={{ textDecoration: "none", ...style }}
    />
  );
}
