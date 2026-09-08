"use client";

import { Search } from "lucide-react";
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
    <div className="space-y-6">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-automl-ink dark:text-white">
            {t("header.title")}
          </h1>
          <p className="mt-2 text-sm font-medium text-automl-muted dark:text-white/60">
            {t("header.subtitle")}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-3">
          <span className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 shadow-sm dark:border-white/10 dark:bg-white/10 dark:text-white">
            <span className="text-slate-400 dark:text-white/50">{t("header.totalTemplates")}:</span>
            <span className="font-black text-slate-900 dark:text-white">{total}</span>
          </span>
          <span className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 text-sm font-bold text-emerald-700 shadow-sm dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
            <span>{t("header.readyToUse")}:</span>
            <span className="font-black">{ready}</span>
          </span>
        </div>
      </section>

      <div className="max-w-xl">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            placeholder={t("header.searchPlaceholder")}
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 pl-11 text-sm font-bold text-automl-ink outline-none transition placeholder:text-slate-400 focus:border-automl-blue focus:ring-4 focus:ring-automl-blue/10 dark:border-white/10 dark:bg-white/10 dark:text-white"
          />
        </div>
      </div>
    </div>
  );
}
