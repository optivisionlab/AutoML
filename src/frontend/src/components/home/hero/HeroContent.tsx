"use client";

import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";

const chipKeys = ["chip1", "chip2", "chip3", "chip4"] as const;

export default function HeroContent() {
  const t = useTranslations("Home.hero");

  return (
    <div className="automl-ai-hero-content">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
        className="automl-ai-badge"
      >
        <Sparkles className="h-4 w-4" />
        {t("badge")}
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, delay: 0.08, ease: "easeOut" }}
      >
        {t("titleLine1")}
        <br />
        {t("titleLine2")}
        <br />
        {t("titleLine3")}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, delay: 0.16, ease: "easeOut" }}
        className="automl-ai-description"
      >
        {t("description")}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, delay: 0.24, ease: "easeOut" }}
        className="automl-ai-actions"
      >
        <Link href="/register" className="automl-ai-primary-action">
          {t("primaryAction")}
          <ArrowRight className="h-4 w-4" />
        </Link>
        <Link href="/public-datasets" className="automl-ai-secondary-action">
          {t("secondaryAction")}
        </Link>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.32, ease: "easeOut" }}
        className="automl-ai-chips"
      >
        {chipKeys.map((chipKey) => (
          <span key={chipKey}>{t(`chips.${chipKey}`)}</span>
        ))}
      </motion.div>
    </div>
  );
}
