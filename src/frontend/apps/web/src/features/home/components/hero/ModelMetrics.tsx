"use client";

import type { CSSProperties } from "react";
import { Clock3, Cuboid, TrendingUp } from "lucide-react";
import { useTranslations } from "next-intl";

import type { HeroPointer } from "./HeroSection";

const metrics = [
  {
    labelKey: "accuracy",
    value: "94.7%",
    icon: TrendingUp,
    tone: "primary",
  },
  {
    labelKey: "trainingTime",
    value: "12.4s",
    icon: Clock3,
    tone: "secondary",
  },
  {
    labelKey: "modelsTested",
    value: "128",
    icon: Cuboid,
    tone: "tertiary",
  },
] as const;

type ModelMetricsProps = {
  pointer: HeroPointer;
};

export default function ModelMetrics({ pointer }: ModelMetricsProps) {
  const t = useTranslations("Home.hero.metrics");

  return (
    <div
      className="automl-ai-metrics"
      style={
        {
          "--metric-pointer-x": `${pointer.x * -8}px`,
          "--metric-pointer-y": `${pointer.y * 6}px`,
        } as CSSProperties
      }
    >
      {metrics.map((metric, index) => {
        const Icon = metric.icon;

        return (
          <div
            key={metric.labelKey}
            className={`automl-ai-metric-card ${metric.tone}`}
            style={{ "--metric-delay": `${index * 0.18}s` } as CSSProperties}
          >
            <span className="automl-ai-metric-icon">
              <Icon className="h-4 w-4" />
            </span>
            <span>
              <small>{t(metric.labelKey)}</small>
              <strong>{metric.value}</strong>
            </span>
          </div>
        );
      })}
    </div>
  );
}
