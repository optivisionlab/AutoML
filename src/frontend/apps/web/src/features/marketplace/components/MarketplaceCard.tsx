"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  ShieldCheck,
} from "lucide-react";
import {
  MarketplaceModel,
} from "@/features/marketplace/data/marketplace";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";

const statusClassName: Record<MarketplaceModel["status"], string> = {
  ready: "bg-emerald-50 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-300",
  beta: "bg-amber-50 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300",
  internal: "bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-white/70",
};

export default function MarketplaceCard({ model }: { model: MarketplaceModel }) {
  const t = useTranslations("Marketplace");

  return (
    <Link
      href={`/market-place/${model.slug}`}
      className="group flex h-full flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-automl-blue/40 hover:shadow-xl hover:shadow-slate-900/10 dark:border-white/10 dark:bg-white/10"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-base font-black text-automl-blue ring-1 ring-automl-blue/10">
          {model.shortName}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-black",
                statusClassName[model.status],
              )}
            >
              {t(`status.${model.status}`)}
            </span>
          </div>
          <h3 className="mt-3 line-clamp-2 text-xl font-black text-automl-ink dark:text-white">
            {model.name}
          </h3>
          <p className="mt-1 text-xs font-bold text-automl-muted dark:text-white/55">
            {model.owner}
          </p>
        </div>
        <ArrowUpRight className="h-5 w-5 text-slate-300 transition group-hover:text-automl-blue" />
      </div>

      <p className="mt-5 line-clamp-3 text-sm leading-6 text-automl-muted-strong dark:text-white/60">
        {model.shortDescription}
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {model.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-white/60"
          >
            {tag}
          </span>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-3 gap-3 text-center">
        <Metric icon={Gauge} label={t("card.metric")} value={model.metrics.accuracy} />
        <Metric icon={Clock3} label={t("card.latency")} value={model.metrics.latency} />
        <Metric icon={Database} label={t("card.runs")} value={model.metrics.runs} />
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs font-bold text-automl-muted dark:border-white/10 dark:text-white/55">
        <span className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          {t("card.updated", { date: model.updatedAt })}
        </span>
        <span className="flex items-center gap-2 text-automl-blue">
          <ShieldCheck className="h-4 w-4" />
          {t("card.viewDetails")}
        </span>
      </div>
    </Link>
  );
}

const Metric = ({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
}) => (
  <div className="rounded-2xl bg-slate-50 p-3 dark:bg-white/5">
    <Icon className="mx-auto h-4 w-4 text-automl-blue" />
    <p className="mt-2 truncate text-sm font-black text-automl-ink dark:text-white">
      {value}
    </p>
    <p className="mt-1 text-[11px] font-bold text-automl-muted dark:text-white/45">
      {label}
    </p>
  </div>
);
