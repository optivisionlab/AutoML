"use client";

import Image from "next/image";
import Link from "next/link";
import {
  BrainCircuit,
  Database,
  GitBranch,
  Mail,
  MapPin,
  Rocket,
  Workflow,
} from "lucide-react";
import { FaFacebook, FaYoutube } from "react-icons/fa";

import HeroSection from "@/components/home/hero/HeroSection";
import MemberLab from "@/components/memberLab/MemberLab";
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

const footerGroups = [
  ["footer.product", "footer.workflowCanvas", "footer.autoTrain", "footer.deployTest"],
  ["footer.resources", "footer.publicDatasets", "footer.marketplace", "footer.trainingHistory"],
  ["footer.research", "footer.optivisionLab", "footer.haui", "footer.openSource"],
  ["footer.links", "footer.github", "footer.community", "footer.docs"],
];

export default function Home() {
  const t = useTranslations("Home");

  return (
    <main className="min-h-screen overflow-hidden bg-automl-canvas text-automl-ink">
      <HeroSection />

      <section className="px-4 sm:px-6 lg:px-8">
        <div className="mx-auto mt-10 grid max-w-6xl gap-4 border-y border-automl-line py-5 md:grid-cols-[1.55fr_repeat(3,1fr)]">
          <p className="text-base font-black leading-6 text-automl-ink">
            {t("statsIntro")}
          </p>
          {stats.map(([value, label]) => (
            <div key={label} className="md:text-center">
              <p className="text-3xl font-black text-automl-ink">{value}</p>
              <p className="text-sm font-bold text-automl-muted">{t(label)}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="workflow" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-end">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-automl-line bg-automl-surface px-4 py-2 text-sm font-bold text-automl-muted">
                <Workflow className="h-4 w-4 text-automl-blue" />
                {t("workflowBadge")}
              </div>
              <h2 className="mt-5 text-4xl font-black leading-tight text-automl-ink sm:text-5xl">
                {t("workflowTitle")}
              </h2>
            </div>
            <p className="text-base font-semibold leading-7 text-automl-muted">
              {t("workflowBody")}
            </p>
          </div>

          <div className="mt-9 grid gap-4 md:grid-cols-3">
            {valueCards.map((card) => {
              const Icon = card.icon;

              return (
                <article
                  key={card.titleKey}
                  className="rounded-lg border border-automl-line bg-automl-surface p-6"
                >
                  <div className={`flex h-11 w-11 items-center justify-center rounded-lg ${card.tone}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-6 text-2xl font-black leading-tight text-automl-ink">
                    {t(card.titleKey)}
                  </h3>
                  <p className="mt-5 text-base font-semibold leading-7 text-automl-muted">
                    {t(card.bodyKey)}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="marketplace" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 rounded-lg border border-automl-line bg-automl-navy px-6 py-8 text-white md:grid-cols-[0.95fr_1.05fr] md:px-8">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-bold text-slate-300">
              <BrainCircuit className="h-4 w-4 text-cyan-300" />
              {t("marketplaceBadge")}
            </div>
            <h2 className="mt-5 max-w-xl text-4xl font-black leading-tight sm:text-5xl">
              {t("marketplaceTitle")}
            </h2>
            <p className="mt-5 max-w-xl text-base font-semibold leading-7 text-slate-300">
              {t("marketplaceBody")}
            </p>
            <Link
              href="/market-place"
              className="mt-8 inline-flex h-12 items-center justify-center rounded-lg bg-automl-blue px-6 text-sm font-bold text-white transition hover:bg-automl-blue-hover"
            >
              {t("exploreMarketplace")}
            </Link>
          </div>

          <div className="grid gap-3">
            {templates.map((item, index) => (
              <div
                key={item.title}
                className="grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-lg border border-white/10 bg-white/5 px-4 py-4"
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
                <span className="rounded-full bg-emerald-400/12 px-4 py-2 text-sm font-black text-emerald-300">
                  {item.badge}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="product" className="px-4 py-16 text-center sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-4xl font-black leading-tight text-automl-ink sm:text-5xl">
            {t("productTitle")}
          </h2>
          <p className="mx-auto mt-5 max-w-3xl text-base font-semibold leading-7 text-automl-muted">
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

      <section id="introduction" className="border-y border-automl-line bg-automl-surface px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.82fr_1.18fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-automl-line bg-automl-surface-muted px-4 py-2 text-sm font-bold text-automl-muted">
              <Workflow className="h-4 w-4 text-automl-blue" />
              {t("introBadge")}
            </div>
            <h2 className="mt-5 text-4xl font-black text-automl-ink">
              {t("introTitle")}
            </h2>
          </div>
          <div className="space-y-6 text-base font-semibold leading-8 text-automl-muted">
            <p>
              {t("introBodyPrefix")}{" "}
              <strong className="font-black text-automl-blue">
                HYPER-PROCESSOR AUTOMATED MACHINE LEARNING
              </strong>
              . {t("introBodySuffix")}
            </p>
            <p>
              {t("introLowCode")}
            </p>
          </div>
        </div>
      </section>

      <section id="about-us" className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto mb-10 max-w-3xl text-center">
            <h2 className="text-4xl font-black text-automl-ink">
              {t("aboutTitle")}
            </h2>
            <p className="mt-5 text-base font-semibold leading-7 text-automl-muted">
              {t("aboutBody")}
            </p>
          </div>
          <MemberLab />
        </div>
      </section>

      <footer id="contact" className="bg-automl-navy px-4 py-14 text-white sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-[1.05fr_0.95fr]">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white">
                <Image
                  src="/logoHautoMLNotext.png"
                  alt="HAutoML"
                  width={30}
                  height={30}
                  className="h-8 w-8 object-contain"
                />
              </div>
              <div>
                <p className="text-xl font-black">HAutoML</p>
                <p className="text-sm font-semibold text-slate-400">
                  Open AutoML Studio
                </p>
              </div>
            </div>

            <p className="mt-6 max-w-xl text-sm font-semibold leading-6 text-slate-300">
              {t("footerDescription")}
            </p>

            <div className="mt-7 space-y-3 text-sm font-semibold text-slate-300">
              <div className="flex items-start gap-3">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
                <span>
                  {t("address")}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 text-cyan-300" />
                <a href="mailto:optivision.work@gmail.com" className="hover:text-white">
                  optivision.work@gmail.com
                </a>
              </div>
            </div>

            <div className="mt-8 flex items-center gap-4 text-slate-400">
              <span className="text-xs">© 2026 OptivisionLab</span>
              <Link
                href="https://www.facebook.com/meoluoiai"
                className="text-blue-300 hover:text-blue-200"
                aria-label="Facebook"
              >
                <FaFacebook className="h-5 w-5" />
              </Link>
              <Link
                href="https://www.youtube.com/@meoluoiai"
                className="text-red-300 hover:text-red-200"
                aria-label="YouTube"
              >
                <FaYoutube className="h-5 w-5" />
              </Link>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {footerGroups.map(([title, ...links]) => (
              <div key={title} className="rounded-lg border border-white/10 p-5">
                <p className="font-black">{t(title)}</p>
                <div className="mt-4 space-y-2">
                  {links.map((item) => (
                    <p key={item} className="text-sm font-semibold text-slate-400">
                      {t(item)}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </footer>
    </main>
  );
}
