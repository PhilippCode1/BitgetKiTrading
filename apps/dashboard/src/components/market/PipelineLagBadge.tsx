"use client";

import type { LagBucket } from "@/lib/market-universe-stream-pulse";

type Props = Readonly<{
  lagMs: number | null;
  bucket: LagBucket;
  labelTemplate: string;
}>;

export function PipelineLagBadge({ lagMs, bucket, labelTemplate }: Props) {
  const text =
    lagMs != null && Number.isFinite(lagMs)
      ? labelTemplate.replace("{ms}", String(Math.round(lagMs)))
      : "—";
  const cls =
    bucket === "ok"
      ? "market-pulse__lag market-pulse__lag--ok"
      : bucket === "warn"
        ? "market-pulse__lag market-pulse__lag--warn"
        : bucket === "bad"
          ? "market-pulse__lag market-pulse__lag--bad"
          : "market-pulse__lag market-pulse__lag--unk";
  return (
    <span className={cls} title={text} data-testid="pipeline-lag-badge">
      {text}
    </span>
  );
}
