type Props = Readonly<{
  warnings: unknown[];
  t?: (key: string) => string;
}>;

export function RiskWarningsPanel({ warnings, t }: Props) {
  if (!warnings.length) return null;
  return (
    <div className="panel">
      <h2>{t ? t("pages.signalsDetail.riskWarningsTitle") : "Risiko-Hinweise"}</h2>
      <ul className="warnings">
        {warnings.map((w, i) => (
          <li key={i}>{typeof w === "string" ? w : JSON.stringify(w)}</li>
        ))}
      </ul>
    </div>
  );
}
