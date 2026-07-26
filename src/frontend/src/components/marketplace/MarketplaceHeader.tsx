"use client";

import { Search, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

type MarketplaceHeaderProps = {
  searchValue: string;
  onSearchChange: (value: string) => void;
  total: number;
  ready: number;
};

export default function MarketplaceHeader({
  searchValue,
  onSearchChange,
  total,
  ready,
}: MarketplaceHeaderProps) {
  const t = useTranslations("Marketplace");

  return (
    <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full bg-automl-blue-soft px-4 py-2 text-xs font-black text-automl-blue">
            <Sparkles className="h-4 w-4" />
            {t("header.eyebrow")}
          </span>
          <h1 className="mt-5 text-4xl font-black tracking-tight text-automl-ink dark:text-white">
            {t("header.title")}
          </h1>
          <p className="mt-3 text-base leading-7 text-automl-muted dark:text-white/60">
            {t("header.subtitle")}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:w-[360px]">
          <div className="rounded-3xl bg-slate-50 p-4 dark:bg-white/5">
            <p className="text-xs font-bold text-automl-muted dark:text-white/50">
              {t("header.totalTemplates")}
            </p>
            <p className="mt-2 text-3xl font-black text-automl-ink dark:text-white">
              {total}
            </p>
          </div>
          <div className="rounded-3xl bg-emerald-50 p-4 dark:bg-emerald-400/10">
            <p className="text-xs font-bold text-emerald-700 dark:text-emerald-300">
              {t("header.readyToUse")}
            </p>
            <p className="mt-2 text-3xl font-black text-emerald-700 dark:text-emerald-300">
              {ready}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 max-w-xl">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            placeholder={t("header.searchPlaceholder")}
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm font-bold text-automl-ink outline-none transition placeholder:text-slate-400 focus:border-automl-blue focus:bg-white focus:ring-4 focus:ring-automl-blue/10 dark:border-white/10 dark:bg-white/10 dark:text-white"
          />
        </div>
      </div>
    </section>
  );
}
