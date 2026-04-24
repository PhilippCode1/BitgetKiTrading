"use client";

import { vpinWarningLevel } from "@/lib/market-universe-stream-pulse";

type Props = Readonly<{
  values: readonly number[];
  lastVpin: number | null;
}>;

const W = 88;
const H = 28;
const PAD = 2;

export function VpinSparkline({ values, lastVpin }: Props) {
  const warn = vpinWarningLevel(lastVpin);
  const strokeClass =
    warn === "halt"
      ? "market-pulse__spark--halt"
      : warn === "caution"
        ? "market-pulse__spark--caution"
        : "market-pulse__spark--ok";
  if (values.length < 2) {
    return (
      <div
        className="market-pulse__spark-wrap"
        data-testid="vpin-sparkline"
        title={
          lastVpin != null && Number.isFinite(lastVpin)
            ? `VPIN ${lastVpin.toFixed(3)}`
            : "VPIN"
        }
      >
        <span className="mono-small muted">—</span>
      </div>
    );
  }
  const minX = 0;
  const maxX = Math.max(0, values.length - 1);
  const minY = 0;
  const maxY = 1;
  const innerW = W - 2 * PAD;
  const innerH = H - 2 * PAD;
  const pts = values.map((y, i) => {
    const t = (i - minX) / (maxX - minX || 1);
    const u = (y - minY) / (maxY - minY || 1);
    const px = PAD + t * innerW;
    const py = PAD + innerH * (1 - u);
    return `${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
  });
  const d = pts.join(" ");
  return (
    <div
      className="market-pulse__spark-wrap"
      data-testid="vpin-sparkline"
      title={
        lastVpin != null && Number.isFinite(lastVpin)
          ? `VPIN ${lastVpin.toFixed(3)}`
          : "VPIN"
      }
    >
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        className={`market-pulse__spark ${strokeClass}`}
        aria-hidden
      >
        <path
          d={d}
          fill="none"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}
