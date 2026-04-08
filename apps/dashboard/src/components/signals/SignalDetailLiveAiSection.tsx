import type { ReactNode } from "react";

type Translate = (
  key: string,
  vars?: Record<string, string | number>,
) => string;

type Props = Readonly<{
  children: ReactNode;
  t: Translate;
}>;

/** Schicht: Live-KI (auf Anfrage) + Strategie-Entwurf — unterhalb gespeicherter Erklärung. */
export function SignalDetailLiveAiSection({ children, t }: Props) {
  return (
    <section className="signal-explain-llm-wrap signal-detail-live-ai">
      <div className="signal-explain-llm-wrap__ribbon">
        <span className="status-pill status-warn">
          {t("pages.signalsDetail.badgeLiveLlm")}
        </span>
        <span className="muted small">
          {t("pages.signalsDetail.aiStrategyChartHint")}
        </span>
      </div>
      {children}
    </section>
  );
}
