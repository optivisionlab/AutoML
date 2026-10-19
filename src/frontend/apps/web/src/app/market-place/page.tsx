"use client";

import { useMemo, useState } from "react";
import { Clock, Filter, PackageOpen, Sparkles } from "lucide-react";
import MarketplaceCard from "@/features/marketplace/components/MarketplaceCard";
import MarketplaceHeader from "@/features/marketplace/components/MarketplaceHeader";
import {
  marketplaceCategories,
  marketplaceModels,
  MarketplaceModelStatus,
} from "@/features/marketplace/data/marketplace";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";

const statusFilters: Array<{ id: "all" | MarketplaceModelStatus }> = [
  { id: "all" },
  { id: "ready" },
  { id: "beta" },
  { id: "internal" },
];

export default function MarketplacePage() {
  const t = useTranslations("Marketplace");
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState<
    "all" | MarketplaceModelStatus
  >("all");
  const [devNoticeOpen, setDevNoticeOpen] = useState(true);

  const filteredModels = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return marketplaceModels.filter((model) => {
      const matchesCategory =
        selectedCategory === "all" || model.category === selectedCategory;
      const matchesStatus =
        selectedStatus === "all" || model.status === selectedStatus;
      const searchable = [
        model.name,
        model.useCase,
        model.shortDescription,
        model.owner,
        ...model.tags,
      ]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !keyword || searchable.includes(keyword);

      return matchesCategory && matchesStatus && matchesSearch;
    });
  }, [search, selectedCategory, selectedStatus]);

  const readyCount = marketplaceModels.filter(
    (model) => model.status === "ready",
  ).length;

  return (
    <div className="space-y-6">
      {/* Hộp thoại thông báo nổi lên khi vào trang */}
      <Dialog open={devNoticeOpen} onOpenChange={setDevNoticeOpen}>
        <DialogContent className="max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-slate-950 sm:max-w-md">
          <div className="flex flex-col items-center text-center">
            <div className="relative mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500 ring-1 ring-amber-500/25">
              <Sparkles className="h-7 w-7 text-amber-500" />
              <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500"></span>
              </span>
            </div>

            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-black text-amber-600 dark:text-amber-400">
              <Clock className="h-3.5 w-3.5" />
              <span>{t("devNotice.badge")}</span>
            </div>

            <DialogTitle className="text-xl font-black text-automl-ink dark:text-white">
              {t("devNotice.title")}
            </DialogTitle>

            <DialogDescription className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
              {t("devNotice.description")}
            </DialogDescription>

            <div className="mt-6 w-full">
              <Button
                onClick={() => setDevNoticeOpen(false)}
                className="w-full h-11 rounded-2xl bg-blue-600 text-sm font-bold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-500 transition-all active:scale-[0.98]"
              >
                {t("devNotice.dismissButton")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Banner thông báo ghim cố định phía trên */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-900 dark:text-amber-200">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <p className="text-xs sm:text-sm font-medium leading-relaxed">
            <strong className="font-black text-amber-800 dark:text-amber-300">{t("devNotice.bannerPrefix")}</strong>{" "}
            {t("devNotice.bannerText")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setDevNoticeOpen(true)}
          className="shrink-0 text-xs font-black text-amber-700 hover:text-amber-800 dark:text-amber-300 underline underline-offset-4 transition"
        >
          {t("devNotice.viewNotice")}
        </button>
      </div>

      <MarketplaceHeader
        searchValue={search}
        onSearchChange={setSearch}
        total={marketplaceModels.length}
        ready={readyCount}
      />

      <section className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <aside className="space-y-4 rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="flex items-center gap-2 text-sm font-black text-automl-ink dark:text-white">
            <Filter className="h-4 w-4 text-automl-blue" />
            {t("filters.title")}
          </div>

          <FilterGroup
            title={t("filters.category")}
            items={marketplaceCategories}
            value={selectedCategory}
            onChange={setSelectedCategory}
            getLabel={(id) => t(`categories.${id}`)}
          />

          <FilterGroup
            title={t("filters.status")}
            items={statusFilters}
            value={selectedStatus}
            onChange={(value) =>
              setSelectedStatus(value as "all" | MarketplaceModelStatus)
            }
            getLabel={(id) => t(`statusFilters.${id}`)}
          />
        </aside>

        <main className="min-w-0">
          <div className="mb-4 flex items-center justify-between gap-4">
            <p className="text-sm font-bold text-automl-muted dark:text-white/55">
              {t("summary", { shown: filteredModels.length, total: marketplaceModels.length })}
            </p>
            <span className="rounded-full bg-slate-100 px-4 py-2 text-xs font-black text-slate-500 dark:bg-white/10 dark:text-white/60">
              {t("sortUpdated")}
            </span>
          </div>

          {filteredModels.length > 0 ? (
            <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
              {filteredModels.map((model) => (
                <MarketplaceCard key={model.id} model={model} />
              ))}
            </div>
          ) : (
            <div className="flex min-h-72 flex-col items-center justify-center rounded-[2rem] border border-dashed border-slate-300 bg-white p-8 text-center dark:border-white/15 dark:bg-white/10">
              <PackageOpen className="h-10 w-10 text-slate-400" />
              <h2 className="mt-4 text-xl font-black text-automl-ink dark:text-white">
                {t("empty.title")}
              </h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-automl-muted dark:text-white/55">
                {t("empty.body")}
              </p>
            </div>
          )}
        </main>
      </section>
    </div>
  );
}

const FilterGroup = ({
  title,
  items,
  value,
  onChange,
  getLabel,
}: {
  title: string;
  items: Array<{ id: string; name?: string }>;
  value: string;
  onChange: (value: string) => void;
  getLabel: (id: string, fallback?: string) => string;
}) => (
  <div>
    <p className="mb-3 text-xs font-black uppercase tracking-wide text-slate-400">
      {title}
    </p>
    <div className="space-y-2">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={cn(
            "flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left text-sm font-bold transition",
            value === item.id
              ? "bg-automl-blue-soft text-automl-blue"
              : "text-slate-500 hover:bg-slate-100 hover:text-automl-ink dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white",
          )}
        >
          {getLabel(item.id, item.name)}
          {value === item.id && <span className="h-2 w-2 rounded-full bg-automl-blue" />}
        </button>
      ))}
    </div>
  </div>
);
