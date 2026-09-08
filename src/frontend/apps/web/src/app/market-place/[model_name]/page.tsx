"use client";

import { useParams } from "next/navigation";
import {
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  Play,
  Rocket,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  getMarketplaceModelBySlug,
  marketplaceStatusLabels,
} from "@/features/marketplace/data/marketplace";
import BackButton from "@/shared/components/common/BackButton";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import { useToast } from "@/shared/hooks/use-toast";
import { useTranslations } from "next-intl";

const tabKeys = ["overview", "io", "test", "api"] as const;

export default function MarketplaceDetailPage() {
  const params = useParams();
  const { toast } = useToast();
  const common = useTranslations("Common");
  const t = useTranslations("Marketplace");
  const slug = params?.model_name as string;
  const model = getMarketplaceModelBySlug(slug);

  if (!model) {
    return (
      <div className="rounded-[2rem] border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-white/10 dark:bg-white/10">
        <h1 className="text-2xl font-black text-automl-ink dark:text-white">
          {t("detail.notFound")}
        </h1>
        <p className="mt-2 text-sm text-automl-muted dark:text-white/55">
          {t("detail.notFoundDesc")}
        </p>
        <div className="mt-6 flex justify-center">
          <BackButton
            fallbackHref="/market-place"
            label={t("detail.backToStore")}
            variant="primary"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Banner thông báo phát triển */}
      <div className="flex items-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-900 dark:text-amber-200">
        <Sparkles className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
        <p className="text-xs sm:text-sm font-medium">
          <strong className="font-black text-amber-800 dark:text-amber-300">{t("devNotice.bannerPrefix")}</strong>{" "}
          {t("devNotice.detailBannerText")}
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <BreadcrumbNav
          items={[
            { label: "Marketplace", href: "/market-place" },
            { label: model.name },
          ]}
        />
        <BackButton
          fallbackHref="/market-place"
          label={common("backToModelStore")}
          variant="ghost"
        />
      </div>

      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex gap-5">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl bg-automl-blue-soft text-2xl font-black text-automl-blue">
              {model.shortName}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-automl-blue-soft px-3 py-1 text-xs font-black text-automl-blue">
                  {marketplaceStatusLabels[model.status]}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-white/60">
                  {t("detail.updated", { date: model.updatedAt })}
                </span>
              </div>
              <h1 className="mt-4 text-4xl font-black tracking-tight text-automl-ink dark:text-white">
                {model.name}
              </h1>
              <p className="mt-3 max-w-3xl text-base leading-7 text-automl-muted dark:text-white/60">
                {model.description}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              toast({
                title: t("devNotice.toastTitle"),
                description: t("devNotice.toastDescription"),
              });
            }}
            className="inline-flex h-12 shrink-0 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-automl-blue to-cyan-500 px-5 text-sm font-black text-white shadow-sm transition hover:opacity-95"
          >
            <Play className="h-4 w-4" />
            {t("detail.useTemplate")}
          </button>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <MetricCard icon={Gauge} label={t("detail.primaryMetric")} value={model.metrics.accuracy} />
          <MetricCard icon={Clock3} label={t("detail.latency")} value={model.metrics.latency} />
          <MetricCard icon={Database} label={t("detail.runs")} value={model.metrics.runs} />
          <MetricCard icon={ShieldCheck} label={t("detail.owner")} value={model.owner} />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <main className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-4 dark:border-white/10">
            {tabKeys.map((key, index) => (
              <span
                key={key}
                className={
                  index === 0
                    ? "rounded-2xl bg-automl-blue px-4 py-2 text-sm font-black text-white"
                    : "rounded-2xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-500 dark:bg-white/10 dark:text-white/60"
                }
              >
                {t("detail.tabs." + key)}
              </span>
            ))}
          </div>

          <div className="mt-6 space-y-8">
            <ContentSection title={t("detail.useCase")} body={model.useCase} />

            <section>
              <h2 className="text-xl font-black text-automl-ink dark:text-white">
                {t("detail.keyFeatures")}
              </h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {model.features.map((feature) => (
                  <div
                    key={feature}
                    className="flex gap-3 rounded-2xl bg-slate-50 p-4 dark:bg-white/5"
                  >
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    <p className="text-sm font-semibold leading-6 text-slate-600 dark:text-white/70">
                      {feature}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <IOPanel title={t("detail.inputs")} items={model.inputs} />
              <IOPanel title={t("detail.outputs")} items={model.outputs} />
            </section>

            <section>
              <h2 className="text-xl font-black text-automl-ink dark:text-white">
                {t("detail.internalApi")}
              </h2>
              <div className="mt-4 rounded-2xl bg-slate-950 p-4 text-sm text-cyan-100">
                <code>POST {model.endpoint}</code>
              </div>
            </section>
          </div>
        </main>

        <aside className="space-y-6">
          <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
            <h2 className="text-xl font-black text-automl-ink dark:text-white">
              {t("detail.checklistTitle")}
            </h2>
            <div className="mt-5 space-y-4">
              {model.checklist.map((item) => (
                <div key={item} className="flex gap-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-automl-blue" />
                  <p className="text-sm font-semibold leading-6 text-automl-muted-strong dark:text-white/60">
                    {item}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-automl-blue/20 bg-automl-blue-soft p-6">
            <Rocket className="h-8 w-8 text-automl-blue" />
            <h2 className="mt-4 text-xl font-black text-automl-ink">
              {t("detail.readyTitle")}
            </h2>
            <p className="mt-2 text-sm leading-6 text-automl-muted-strong">
              {t("detail.readyDesc")}
            </p>
          </div>
        </aside>
      </section>
    </div>
  );
}

const MetricCard = ({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
}) => (
  <div className="rounded-3xl bg-slate-50 p-4 dark:bg-white/5">
    <Icon className="h-5 w-5 text-automl-blue" />
    <p className="mt-3 text-xs font-bold text-automl-muted dark:text-white/50">
      {label}
    </p>
    <p className="mt-1 truncate text-lg font-black text-automl-ink dark:text-white">
      {value}
    </p>
  </div>
);

const ContentSection = ({ title, body }: { title: string; body: string }) => (
  <section>
    <h2 className="text-xl font-black text-automl-ink dark:text-white">
      {title}
    </h2>
    <p className="mt-3 text-sm leading-7 text-automl-muted-strong dark:text-white/60">
      {body}
    </p>
  </section>
);

const IOPanel = ({ title, items }: { title: string; items: string[] }) => (
  <div className="rounded-3xl border border-slate-200 p-5 dark:border-white/10">
    <h3 className="font-black text-automl-ink dark:text-white">{title}</h3>
    <div className="mt-4 flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-white/60"
        >
          {item}
        </span>
      ))}
    </div>
  </div>
);
