"use client";

import Link from "next/link";
import {
  Database,
  GitBranch,
  Rocket,
} from "lucide-react";

import HeroSection from "@/features/home/components/hero/HeroSection";
import IntroductionSection from "@/features/home/components/sections/introduction/IntroductionSection";
import ProductionPipeline from "@/features/home/components/sections/production-pipeline/ProductionPipeline";
import IndustryShowcase from "@/features/home/components/sections/industry-showcase/IndustryShowcase";
import { useTranslations } from "next-intl";

const stats = [
  ["8+", "stats.algorithms"],
  ["4", "stats.sampleSources"],
  ["1-click", "stats.deployTest"],
];

const valueCards = [
  {
    icon: Database,
    titleKey: "cards.realData.title",
    bodyKey: "cards.realData.body",
    tone: "bg-automl-cyan-soft text-cyan-700 dark:text-cyan-200",
  },
  {
    icon: GitBranch,
    titleKey: "cards.pipeline.title",
    bodyKey: "cards.pipeline.body",
    tone: "bg-automl-blue-soft text-blue-700 dark:text-blue-200",
  },
  {
    icon: Rocket,
    titleKey: "cards.deploy.title",
    bodyKey: "cards.deploy.body",
    tone: "bg-automl-green-soft text-emerald-700 dark:text-emerald-200",
  },
];

const templates = [
  {
    title: "Glass classification",
    path: "table -> preprocess -> KNN",
    badge: "65.92%",
  },
  {
    title: "Credit approval",
    path: "cleaning -> ensemble -> deploy",
    badge: "ready",
  },
  {
    title: "Customer churn",
    path: "feature engineering -> XGBoost",
    badge: "ROC 0.793",
  },
];

export default function Home() {
  const t = useTranslations("Home");

  return (
    <main className="min-h-screen overflow-hidden bg-white text-automl-ink dark:bg-[#070A13]">
      {/* 1. Hero 3D Component */}
      <HeroSection />

      {/* 2. Giới thiệu ngắn về Hệ thống HAutoML */}
      <IntroductionSection />

      {/* 3. Quy trình AutoML phân tán trực quan */}
      <ProductionPipeline />

      {/* 4. Chứng thực thành tích, giải thưởng & lĩnh vực ứng dụng đa ngành theo mẫu Roboflow */}
      <IndustryShowcase />

      <section className="border-y border-slate-200/80 bg-slate-50/70 px-4 py-10 transition-colors dark:border-white/10 dark:bg-white/[0.02] sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl items-center gap-6 md:grid-cols-[1.55fr_repeat(3,1fr)]">
          <p className="text-base font-black leading-6 text-slate-900 dark:text-white">
            {t("statsIntro")}
          </p>
          {stats.map(([value, label]) => (
            <div key={label} className="md:text-center">
              <p className="text-3xl font-black text-slate-900 dark:text-white">{value}</p>
              <p className="text-sm font-bold text-slate-500 dark:text-slate-400">{t(label)}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="workflow" className="bg-white px-4 py-20 dark:bg-transparent sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
            <div>
              <h2 className="text-4xl font-black leading-tight text-slate-900 sm:text-5xl dark:text-white">
                {t("workflowTitle")}
              </h2>
            </div>
            <p className="text-base font-semibold leading-7 text-slate-600 dark:text-slate-300">
              {t("workflowBody")}
            </p>
          </div>

          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {valueCards.map((card) => {
              const Icon = card.icon;

              return (
                <article
                  key={card.titleKey}
                  className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-blue-300 hover:bg-white hover:shadow-lg dark:border-white/10 dark:bg-white/5 dark:hover:border-white/20"
                >
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${card.tone}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-6 text-xl font-black leading-tight text-slate-900 dark:text-white">
                    {t(card.titleKey)}
                  </h3>
                  <p className="mt-4 text-sm font-semibold leading-relaxed text-slate-600 dark:text-slate-300">
                    {t(card.bodyKey)}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="marketplace" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 rounded-3xl border border-slate-800 bg-[#0B0F19] px-6 py-10 text-white shadow-2xl md:grid-cols-[0.95fr_1.05fr] md:px-10 md:py-12">
          <div>
            <h2 className="max-w-xl text-4xl font-black leading-tight sm:text-5xl">
              {t("marketplaceTitle")}
            </h2>
            <p className="mt-5 max-w-xl text-base font-semibold leading-7 text-slate-300">
              {t("marketplaceBody")}
            </p>
            <Link
              href="/market-place"
              className="mt-8 inline-flex h-12 items-center justify-center rounded-xl bg-automl-blue px-6 text-sm font-bold text-white shadow-md transition hover:bg-automl-blue-hover active:scale-98"
            >
              {t("exploreMarketplace")}
            </Link>
          </div>

          <div className="grid gap-3">
            {templates.map((item, index) => (
              <div
                key={item.title}
                className="grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-xl border border-white/10 bg-white/5 px-4 py-4 backdrop-blur-sm transition hover:border-white/20 hover:bg-white/10"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-sm font-black text-cyan-200">
                  {index + 1}
                </div>
                <div className="min-w-0">
                  <p className="font-black text-white">{item.title}</p>
                  <p className="mt-1 truncate text-sm font-semibold text-slate-400">
                    {item.path}
                  </p>
                </div>
                <span className="rounded-full bg-emerald-400/12 px-4 py-1.5 text-xs font-black text-emerald-300 border border-emerald-400/20">
                  {item.badge}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="product" className="border-t border-slate-200/70 bg-slate-50/60 px-4 py-20 text-center transition-colors dark:border-white/10 dark:bg-[#060b16] sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-4xl font-black leading-tight text-slate-900 sm:text-5xl dark:text-white">
            {t("productTitle")}
          </h2>
          <p className="mx-auto mt-5 max-w-3xl text-base font-semibold leading-7 text-slate-600 dark:text-slate-300">
            {t("productBody")}
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/register" className="automl-button-primary h-12">
              {t("tryFree")}
            </Link>
            <Link href="/training-history" className="automl-button-dark h-12">
              {t("viewTrainingHistory")}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
