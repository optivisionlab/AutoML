"use client";

import type { CSSProperties } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

const chipKeys = ["chip1", "chip2", "chip3", "chip4"] as const;

export default function HeroContent() {
  const t = useTranslations("Home.hero");

  return (
    <div className="automl-ai-hero-content">
      <h1
        className="automl-hero-enter"
        style={{ "--hero-delay": "0.08s", "--hero-y": "16px" } as CSSProperties}
      >
        {t("titleLine1")}
        <br />
        {t("titleLine2")}
        <br />
        {t("titleLine3")}
      </h1>

      <p
        className="automl-ai-description automl-hero-enter"
        style={{ "--hero-delay": "0.16s", "--hero-y": "14px" } as CSSProperties}
      >
        {t("description")}
      </p>

      <div
        className="automl-ai-actions automl-hero-enter"
        style={{ "--hero-delay": "0.24s", "--hero-y": "14px" } as CSSProperties}
      >
        <Link href="/register" className="automl-ai-primary-action">
          {t("primaryAction")}
          <ArrowRight className="h-4 w-4" />
        </Link>
        <Link href="/public-datasets" className="automl-ai-secondary-action">
          {t("secondaryAction")}
        </Link>
      </div>

      <div
        className="automl-ai-chips automl-hero-enter"
        style={{ "--hero-delay": "0.32s", "--hero-y": "12px" } as CSSProperties}
      >
        {chipKeys.map((chipKey) => (
          <span key={chipKey}>{t(`chips.${chipKey}`)}</span>
        ))}
      </div>
    </div>
  );
}
