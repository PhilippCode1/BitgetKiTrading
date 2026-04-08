import type { ComponentProps, ReactNode } from "react";

type Props = Readonly<{
  children: ReactNode;
  /** Zusätzliche Klassen (z. B. Modifikatoren) */
  className?: string;
  as?: "section" | "div";
  id?: string;
  role?: ComponentProps<"section">["role"];
}>;

/**
 * Karten-/Panel-Hülle gemäß Designsystem (`.panel` in globals.css).
 * Reduziert ad-hoc `className="panel"`-Streuer über Seiten hinweg.
 */
export function ContentPanel({
  children,
  className = "",
  as: Tag = "section",
  id,
  role,
}: Props) {
  const cn = ["panel", className.trim()].filter(Boolean).join(" ");
  return (
    <Tag id={id} className={cn} role={role}>
      {children}
    </Tag>
  );
}
