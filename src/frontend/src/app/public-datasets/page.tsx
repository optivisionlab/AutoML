"use client";

import RowActionMenu from "@/components/common/RowActionMenu";
import AppLoading from "@/components/common/AppLoading";
import {
  DataWorkspaceControls,
  DataWorkspaceHeader,
  DataWorkspaceMetrics,
  workspaceInputClass,
} from "@/components/common/DataWorkspace";
import React, { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRouter } from "next/navigation";
import { CalendarClock, Database, Layers3, Search, Sparkles } from "lucide-react";
import { useGetDatasetsByUserIdQuery } from "@/redux/api/datasetApi";
import { useLocale, useTranslations } from "next-intl";

const formatDate = (
  timestamp: number | undefined,
  locale: string,
  fallback: string,
): string => {
  if (!timestamp) return fallback;
  return new Date(timestamp * 1000).toLocaleDateString(locale);
};

const Page = () => {
  const locale = useLocale();
  const t = useTranslations("Datasets");
  const common = useTranslations("Common");
  const { data: datasets = [], isLoading } = useGetDatasetsByUserIdQuery("0");
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"updated" | "name" | "type">("updated");
  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";
  const compareLocale = locale === "vi" ? "vi" : "en";

  const filteredDatasets = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return [...datasets]
      .filter((dataset) => {
        const searchable = [
          dataset.dataName,
          dataset.dataType,
          dataset.username,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return !keyword || searchable.includes(keyword);
      })
      .sort((a, b) => {
        if (sortBy === "name") {
          return (a.dataName || "").localeCompare(b.dataName || "", compareLocale);
        }

        if (sortBy === "type") {
          return (a.dataType || "").localeCompare(b.dataType || "", compareLocale);
        }

        return (
          (b.latestUpdate || b.lastestUpdate || b.createDate || 0) -
          (a.latestUpdate || a.lastestUpdate || a.createDate || 0)
        );
      });
  }, [compareLocale, datasets, search, sortBy]);

  const typeCount = new Set(datasets.map((dataset) => dataset.dataType).filter(Boolean)).size;
  const recentCount = datasets.filter((dataset) => {
    const timestamp = dataset.latestUpdate || dataset.lastestUpdate || dataset.createDate;
    if (!timestamp) return false;

    const daysAgo = (Date.now() - timestamp * 1000) / (1000 * 60 * 60 * 24);
    return daysAgo <= 30;
  }).length;

  return (
    <div className="space-y-6">
      <DataWorkspaceHeader
        eyebrow={t("public.eyebrow")}
        title={t("public.title")}
        subtitle={t("public.subtitle")}
      />

      <DataWorkspaceMetrics
        metrics={[
          {
            label: t("metrics.totalDatasets"),
            value: `${datasets.length}`,
            detail: t("metrics.publicReady"),
            icon: Database,
            tone: "from-blue-100 to-sky-100 text-blue-600",
          },
          {
            label: t("metrics.dataTypes"),
            value: `${typeCount}`,
            detail: t("metrics.dataTypeGroups"),
            icon: Layers3,
            tone: "from-emerald-100 to-teal-100 text-emerald-600",
          },
          {
            label: t("metrics.recentlyUpdated"),
            value: `${recentCount}`,
            detail: t("metrics.last30Days"),
            icon: CalendarClock,
            tone: "from-amber-100 to-orange-100 text-amber-600",
          },
          {
            label: t("metrics.readyToTrain"),
            value: `${datasets.length}`,
            detail: t("metrics.canOpenActions"),
            icon: Sparkles,
            tone: "from-violet-100 to-indigo-100 text-violet-600",
          },
        ]}
      />

      <DataWorkspaceControls
        summary={t("summary", {
          shown: filteredDatasets.length,
          total: datasets.length,
        })}
      >
        <label className="relative min-w-0 sm:w-72">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("searchPlaceholder")}
            className={`${workspaceInputClass} w-full pl-11`}
          />
        </label>
        <select
          value={sortBy}
          onChange={(event) =>
            setSortBy(event.target.value as "updated" | "name" | "type")
          }
          className={`${workspaceInputClass} sm:w-56`}
        >
          <option value="updated">{t("sort.updated")}</option>
          <option value="name">{t("sort.name")}</option>
          <option value="type">{t("sort.type")}</option>
        </select>
      </DataWorkspaceControls>

      <Card className="automl-data-card w-full">
        <CardContent className="automl-table-wrap pt-5">
        {isLoading ? (
          <AppLoading label={common("loadingData")} />
        ) : filteredDatasets.length === 0 ? (
          <div className="automl-state-panel">{t("public.empty")}</div>
        ) : (
          <Table className="automl-data-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("table.name")}</TableHead>
                <TableHead>{t("table.type")}</TableHead>
                <TableHead>{t("table.createdAt")}</TableHead>
                <TableHead>{t("table.updatedAt")}</TableHead>
                <TableHead className="text-center">{common("actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDatasets.map((dataset) => (
                <TableRow key={dataset._id}>
                  <TableCell className="font-bold text-[var(--automl-data-text)]">
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-xs font-black text-automl-blue">
                        {(dataset.dataName || "DS").slice(0, 2).toUpperCase()}
                      </span>
                      <span className="min-w-0 truncate">
                        {dataset.dataName || common("unnamed")}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="automl-data-chip automl-data-chip-secondary">
                      {dataset.dataType || common("unknown")}
                    </span>
                  </TableCell>
                  <TableCell>{formatDate(dataset.createDate, dateLocale, common("noData"))}</TableCell>
                  <TableCell>
                    {formatDate(dataset.latestUpdate || dataset.lastestUpdate, dateLocale, common("noData"))}
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex justify-center">
                      <RowActionMenu
                        label={t("openActions", { name: dataset.dataName || common("unnamed") })}
                        items={[
                          {
                            label: common("train"),
                            onClick: () => router.push(`/public-datasets/${dataset._id}/train`),
                          },
                        ]}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Page;
