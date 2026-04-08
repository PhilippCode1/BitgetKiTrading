import type { OpsModuleId } from "@/lib/upstream-incidents";
import type { TranslateFn } from "@/lib/user-facing-fetch-error";

type Props = Readonly<{
  moduleId: OpsModuleId;
  t: TranslateFn;
}>;

/** Kompakter Hinweis: Modul gehoert zur Kaskade oben, kein wiederholter Volltext. */
export function CollapsedModuleStaleNotice({ moduleId, t }: Props) {
  const name = t(`ui.incident.modules.${moduleId}`);
  return (
    <p className="incident-module-stale muted small" role="status">
      {t("ui.incident.modulePending", { module: name })}
    </p>
  );
}
