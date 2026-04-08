import { HelpHint } from "@/components/help/HelpHint";

type Props = Readonly<{
  title: string;
  subtitle?: string;
  helpBriefKey?: string;
  helpDetailKey?: string;
}>;

export function Header({
  title,
  subtitle,
  helpBriefKey,
  helpDetailKey,
}: Props) {
  return (
    <header className="dash-page-header">
      <div className="dash-page-header-row">
        <h1>{title}</h1>
        {helpBriefKey ? (
          <HelpHint briefKey={helpBriefKey} detailKey={helpDetailKey} />
        ) : null}
      </div>
      {subtitle ? <p className="muted readable">{subtitle}</p> : null}
    </header>
  );
}
