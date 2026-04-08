import Link from "next/link";

import { consolePath } from "@/lib/console-paths";
import {
  connectivitySupplements,
  showConnectivityFirstAid,
} from "@/lib/health-service-reachability";
import type { SystemHealthResponse } from "@/lib/types";

export type HealthTradingReadinessLabels = Readonly<{
  connectivityTitle: string;
  connectivityLead: string;
  connectivityB1: string;
  connectivityB2: string;
  connectivityB3: string;
  connectivityB4: string;
  paperPathTitle: string;
  paperPathLead: string;
  paperStep1: string;
  paperStep2: string;
  paperStep3: string;
  paperStep4: string;
  cockpitCta: string;
  /** Nur wenn Paper + manual — sonst weglassen */
  readinessManualExplainer?: string;
  /** Optional: zusaetzliche <li> unter Erreichbarkeit */
  connectivityExtraMonitorRefused?: string;
  connectivityExtraSplitBrain?: string;
}>;

type Props = Readonly<{
  health: SystemHealthResponse;
  labels: HealthTradingReadinessLabels;
}>;

export function HealthTradingReadinessPanel({ health, labels }: Props) {
  const connectivity = showConnectivityFirstAid(health);
  const extra = connectivity ? connectivitySupplements(health) : null;

  return (
    <div className="panel health-readiness-panel">
      {connectivity ? (
        <div
          className="operator-banner-err"
          role="status"
          style={{ marginBottom: "1rem" }}
        >
          <strong>{labels.connectivityTitle}</strong>
          <p className="small" style={{ marginTop: 8 }}>
            {labels.connectivityLead}
          </p>
          <ul className="news-list small" style={{ marginTop: 8 }}>
            <li>{labels.connectivityB1}</li>
            <li>{labels.connectivityB2}</li>
            <li>{labels.connectivityB3}</li>
            <li>{labels.connectivityB4}</li>
            {extra?.monitorEngineConnectionRefused &&
            labels.connectivityExtraMonitorRefused ? (
              <li>{labels.connectivityExtraMonitorRefused}</li>
            ) : null}
            {extra?.partialReachabilityPattern &&
            labels.connectivityExtraSplitBrain ? (
              <li>{labels.connectivityExtraSplitBrain}</li>
            ) : null}
          </ul>
        </div>
      ) : null}

      <h2>{labels.paperPathTitle}</h2>
      <p className="muted small">{labels.paperPathLead}</p>
      {labels.readinessManualExplainer ? (
        <p className="muted small" style={{ marginTop: 8 }}>
          {labels.readinessManualExplainer}
        </p>
      ) : null}
      <ol
        className="news-list small"
        style={{ marginTop: 12, paddingLeft: "1.25rem" }}
      >
        <li style={{ marginBottom: 8 }}>{labels.paperStep1}</li>
        <li style={{ marginBottom: 8 }}>{labels.paperStep2}</li>
        <li style={{ marginBottom: 8 }}>{labels.paperStep3}</li>
        <li style={{ marginBottom: 8 }}>{labels.paperStep4}</li>
      </ol>
      <p className="muted small" style={{ marginTop: 12 }}>
        <Link href={consolePath("ops")}>{labels.cockpitCta}</Link>
      </p>
    </div>
  );
}
