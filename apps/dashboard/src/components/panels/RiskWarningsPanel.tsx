type Props = Readonly<{
  warnings: unknown[];
}>;

export function RiskWarningsPanel({ warnings }: Props) {
  if (!warnings.length) return null;
  return (
    <div className="panel">
      <h2>Risiko-Hinweise</h2>
      <ul className="warnings">
        {warnings.map((w, i) => (
          <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>
        ))}
      </ul>
    </div>
  );
}
