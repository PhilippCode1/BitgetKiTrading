import Markdown from "react-markdown";

type Props = Readonly<{
  markdown: string | null | undefined;
}>;

export function ExplainMarkdown({ markdown }: Props) {
  if (!markdown) {
    return <p className="muted">Keine Langbeschreibung.</p>;
  }
  return (
    <div className="markdown-body">
      <Markdown>{markdown}</Markdown>
    </div>
  );
}
