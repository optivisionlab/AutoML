"use client";

import { useMemo, useState } from "react";
import { Filter, PackageOpen } from "lucide-react";
import MarketplaceCard from "@/components/marketplace/MarketplaceCard";
import MarketplaceHeader from "@/components/marketplace/MarketplaceHeader";
import {
  marketplaceCategories,
  marketplaceModels,
  MarketplaceModelStatus,
} from "@/data/marketplace";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

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
