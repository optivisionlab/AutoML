"use client";

import RowActionMenu from "@/shared/components/common/RowActionMenu";
import AppLoading from "@/shared/components/common/AppLoading";
import {
  DataWorkspaceControls,
  DataWorkspaceHeader,
  DataWorkspaceMetrics,
  workspaceInputClass,
} from "@/shared/components/common/DataWorkspace";
import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { cn } from "@/shared/lib/utils";
import EditDatasetDialog from "@/features/datasets/components/dataset-dialogs/EditDatasetDialog";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
} from "@/shared/components/ui/alert-dialog";
import { useToast } from "@/shared/hooks/use-toast";
import AddDatasetDialog from "@/features/datasets/components/dataset-dialogs/AddDatasetDialog";
import ConnectDatabaseDialog from "@/features/datasets/components/dataset-dialogs/ConnectDatabaseDialog";
import {
  CalendarClock,
  CirclePlus,
  Database,
  DatabaseZap,
  Layers3,
  LayoutGrid,
  Search,
  Sparkles,
  Table2,
} from "lucide-react";
import {
  Dataset,
  useDeleteDatasetMutation,
  useGetDatasetsByUserIdQuery,
} from "@/core/api/datasetApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { useLocale, useTranslations } from "next-intl";
import PaginationCustom from "@/shared/components/common/Panigation";
import { useAppSettings } from "@/shared/hooks/useAppSettings";
import { DatasetCard } from "@/features/datasets";

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
  const { data: session } = useSession();
  const router = useRouter();
  const userId = session?.user?.id;
  const {
    data: datasets = [],
    isLoading,
    refetch,
  } = useGetDatasetsByUserIdQuery(userId ?? "", {
    skip: !userId,
  });
  const [deleteDataset] = useDeleteDatasetMutation();

  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [datasetIdToDelete, setDatasetIdToDelete] = useState<string | null>(
    null,
  );
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [connectDatabaseOpen, setConnectDatabaseOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"updated" | "name" | "type">("updated");

  const searchParams = useSearchParams();
  const highlightParam = searchParams?.get("highlight") || searchParams?.get("dataset_id");
  const [focusedDatasetId, setFocusedDatasetId] = useState<string | null>(null);
  const [flashDatasetId, setFlashDatasetId] = useState<string | null>(null);

  const { toast } = useToast();
  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";
  const compareLocale = locale === "vi" ? "vi" : "en";

  const availableTypes = useMemo(() => {
    return Array.from(new Set(datasets.map((d) => d.dataType).filter(Boolean))) as string[];
  }, [datasets]);

  const filteredDatasets = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return [...datasets]
      .filter((dataset) => {
        const matchesType = selectedType === "all" || dataset.dataType === selectedType;
        if (!matchesType) return false;

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
  }, [compareLocale, datasets, search, selectedType, sortBy]);

  const { settings, updateSettings } = useAppSettings();
  const viewMode = settings.datasetViewMode || "table";
  const itemsPerPage = settings.tablePageSize || 10;
  const [currentPage, setCurrentPage] = useState<number>(1);

  const totalPages = Math.max(1, Math.ceil(filteredDatasets.length / itemsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedDatasets = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * itemsPerPage;
    return filteredDatasets.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredDatasets, safeCurrentPage, itemsPerPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [search, sortBy, selectedType, itemsPerPage]);

  useEffect(() => {
    if (!highlightParam || filteredDatasets.length === 0) return;

    const matchedIndex = filteredDatasets.findIndex((d) => d._id === highlightParam);
    if (matchedIndex !== -1) {
      const targetPage = Math.floor(matchedIndex / itemsPerPage) + 1;
      setCurrentPage(targetPage);
      setFocusedDatasetId(highlightParam);
      setFlashDatasetId(highlightParam);

      const timer = setTimeout(() => {
        setFlashDatasetId(null);
      }, 3000);

      return () => clearTimeout(timer);
    }
  }, [highlightParam, filteredDatasets, itemsPerPage]);

  const typeCount = new Set(datasets.map((dataset) => dataset.dataType).filter(Boolean)).size;
  const recentCount = datasets.filter((dataset) => {
    const timestamp = dataset.latestUpdate || dataset.lastestUpdate || dataset.createDate;
    if (!timestamp) return false;

    const daysAgo = (Date.now() - timestamp * 1000) / (1000 * 60 * 60 * 24);
    return daysAgo <= 30;
  }).length;

  const handleOpenEdit = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setEditDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!datasetIdToDelete) return;

    try {
      await deleteDataset(datasetIdToDelete).unwrap();

      toast({
        title: t("toast.deleteSuccess"),
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      refetch();
    } catch (err) {
      console.error("Lỗi xoá:", err);
      toast({
        title: t("toast.deleteFailed"),
        description: getApiErrorMessage(
          err,
          t("toast.deleteFailedDescription"),
        ),
        variant: "destructive",
        duration: 3000,
      });
    } finally {
      setDeleteDialogOpen(false);
      setDatasetIdToDelete(null);
    }
  };

  useEffect(() => {
    if (!highlightParam || filteredDatasets.length === 0) return;

    const matchedDataset = filteredDatasets.find(
      (d) =>
        d._id === highlightParam ||
        d.dataName?.toLowerCase().includes(highlightParam.toLowerCase()),
    );
    const target = matchedDataset || filteredDatasets[0];
    if (!target) return;

    setFocusedDatasetId(target._id);
    setFlashDatasetId(target._id);

    const timer = setTimeout(() => {
      const el = document.getElementById(`dataset-row-${target._id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus();
      }
    }, 180);

    const flashTimer = setTimeout(() => setFlashDatasetId(null), 2500);
    return () => {
      clearTimeout(timer);
      clearTimeout(flashTimer);
    };
  }, [highlightParam, filteredDatasets]);

  return (
    <>
      <div className="space-y-6">
        <DataWorkspaceHeader
          eyebrow={t("my.eyebrow")}
          title={t("my.title")}
          subtitle={t("my.subtitle")}
        >
          <Button
            variant="outline"
            className="h-11 gap-2 rounded-2xl border border-slate-200 bg-white px-4 font-bold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15"
            onClick={() => setConnectDatabaseOpen(true)}
          >
            <Database className="h-4 w-4" /> {t("connectDatabase")}
          </Button>
          <Button
            className="automl-action-primary h-11 gap-2 rounded-2xl px-4 font-bold shadow-sm"
            onClick={() => setAddDialogOpen(true)}
          >
            <CirclePlus className="h-4 w-4" /> {t("addDataset")}
          </Button>
        </DataWorkspaceHeader>

        <DataWorkspaceMetrics
          metrics={[
            {
              label: t("metrics.myDatasets"),
              value: `${datasets.length}`,
              detail: t("metrics.managedSources"),
              icon: DatabaseZap,
              tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
            },
            {
              label: t("metrics.dataTypes"),
              value: `${typeCount}`,
              detail: t("metrics.dataTypeGroups"),
              icon: Layers3,
              tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
            },
            {
              label: t("metrics.recentlyUpdated"),
              value: `${recentCount}`,
              detail: t("metrics.last30Days"),
              icon: CalendarClock,
              tone: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
            },
            {
              label: t("metrics.trainable"),
              value: `${datasets.length}`,
              detail: t("metrics.readyForPipeline"),
              icon: Sparkles,
              tone: "bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400",
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

          {availableTypes.length > 0 && (
            <select
              value={selectedType}
              onChange={(event) => setSelectedType(event.target.value)}
              className={`${workspaceInputClass} sm:w-44`}
            >
              <option value="all">{t("allTypes")}</option>
              {availableTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          )}

          <select
            value={sortBy}
            onChange={(event) =>
              setSortBy(event.target.value as "updated" | "name" | "type")
            }
            className={`${workspaceInputClass} sm:w-52`}
          >
            <option value="updated">{t("sort.updated")}</option>
            <option value="name">{t("sort.name")}</option>
            <option value="type">{t("sort.type")}</option>
          </select>

          {/* Phía phải bộ lọc: Bộ chuyển đổi chế độ xem dạng Bảng như cũ HOẶC dạng Lưới/Thẻ như ảnh */}
          <div className="flex items-center rounded-2xl border border-slate-200 bg-slate-100/80 p-1 dark:border-white/10 dark:bg-slate-900">
            <button
              type="button"
              onClick={() => updateSettings({ datasetViewMode: "grid" })}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold transition",
                viewMode === "grid"
                  ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-white"
                  : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white",
              )}
              title={t("viewGrid")}
            >
              <LayoutGrid className="h-4 w-4" />
              <span className="hidden sm:inline">{t("viewGrid")}</span>
            </button>
            <button
              type="button"
              onClick={() => updateSettings({ datasetViewMode: "table" })}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold transition",
                viewMode === "table"
                  ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-white"
                  : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white",
              )}
              title={t("viewTable")}
            >
              <Table2 className="h-4 w-4" />
              <span className="hidden sm:inline">{t("viewTable")}</span>
            </button>
          </div>
        </DataWorkspaceControls>

        {isLoading ? (
          <Card className="automl-data-card w-full">
            <CardContent className="pt-8">
              <AppLoading label={common("loadingData")} />
            </CardContent>
          </Card>
        ) : filteredDatasets.length === 0 ? (
          <Card className="automl-data-card w-full">
            <CardContent className="pt-8">
              <div className="automl-state-panel">{t("empty")}</div>
            </CardContent>
          </Card>
        ) : viewMode === "grid" ? (
          <div className="space-y-6">
            <div className="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {paginatedDatasets.map((dataset) => (
                <DatasetCard
                  key={dataset._id}
                  dataset={dataset}
                  focused={focusedDatasetId === dataset._id}
                  flashing={flashDatasetId === dataset._id}
                  onSelect={() => setFocusedDatasetId(dataset._id)}
                  onTrain={() => router.push(`/my-datasets/${dataset._id}/train`)}
                  onEdit={() => handleOpenEdit(dataset)}
                  onDelete={() => {
                    setDatasetIdToDelete(dataset._id);
                    setDeleteDialogOpen(true);
                  }}
                  trainLabel={common("train")}
                  editLabel={common("edit")}
                  deleteLabel={common("delete")}
                  openActionsLabel={t("openActions", { name: dataset.dataName || common("unnamed") })}
                  formattedDate={formatDate(dataset.createDate, dateLocale, common("noData"))}
                  formattedUpdate={formatDate(
                    dataset.latestUpdate || dataset.lastestUpdate,
                    dateLocale,
                    common("noData"),
                  )}
                />
              ))}
            </div>

            <PaginationCustom
              currentPage={safeCurrentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          </div>
        ) : (
          <Card className="automl-data-card w-full">
            <CardContent className="automl-table-wrap pt-5">
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
                  {paginatedDatasets.map((dataset) => (
                    <TableRow
                      key={dataset._id}
                      id={`dataset-row-${dataset._id}`}
                      tabIndex={0}
                      onClick={() => setFocusedDatasetId(dataset._id)}
                      onFocus={() => setFocusedDatasetId(dataset._id)}
                      className={cn(
                        "cursor-pointer transition-all outline-none",
                        focusedDatasetId === dataset._id && "automl-row-focused",
                        flashDatasetId === dataset._id && "automl-row-flash",
                      )}
                      data-focused={focusedDatasetId === dataset._id}
                    >
                      <TableCell className="font-bold text-[var(--automl-data-text)]">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-automl-blue-soft text-[11px] font-black text-automl-blue">
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
                        {formatDate(
                          dataset.latestUpdate || dataset.lastestUpdate,
                          dateLocale,
                          common("noData"),
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex justify-center">
                          <RowActionMenu
                            label={t("openActions", { name: dataset.dataName || common("unnamed") })}
                            items={[
                              {
                                label: common("train"),
                                onClick: () => router.push(`/my-datasets/${dataset._id}/train`),
                              },
                              { label: common("edit"), onClick: () => handleOpenEdit(dataset) },
                              {
                                label: common("delete"),
                                destructive: true,
                                onClick: () => {
                                  setDatasetIdToDelete(dataset._id);
                                  setDeleteDialogOpen(true);
                                },
                              },
                            ]}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <PaginationCustom
                currentPage={safeCurrentPage}
                totalPages={totalPages}
                onPageChange={setCurrentPage}
              />
            </CardContent>
          </Card>
        )}
      </div>

      {selectedDataset && (
        <EditDatasetDialog
          open={editDialogOpen}
          onOpenChange={(open) => {
            setEditDialogOpen(open);
            if (!open) refetch();
          }}
          dataset={selectedDataset}
        />
      )}

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="automl-dialog-content max-w-md">
          <AlertDialogHeader className="automl-dialog-header">
            <AlertDialogTitle className="automl-dialog-title">
              {t("deleteDialog.title")}
            </AlertDialogTitle>
            <AlertDialogDescription className="automl-dialog-description">
              {t("deleteDialog.description")}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter className="automl-dialog-footer">
            <AlertDialogCancel className="automl-dialog-button-muted mt-0">
              {common("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="automl-action-danger"
            >
              {common("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {session?.user?.id && (
        <AddDatasetDialog
          open={addDialogOpen}
          onOpenChange={setAddDialogOpen}
          userId={session.user.id}
          onSuccess={refetch}
        />
      )}

      <ConnectDatabaseDialog
        open={connectDatabaseOpen}
        onOpenChange={setConnectDatabaseOpen}
      />
    </>
  );
};

export default Page;
