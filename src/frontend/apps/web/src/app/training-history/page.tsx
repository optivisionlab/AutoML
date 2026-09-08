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
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { cn } from "@/shared/lib/utils";

import { Card, CardContent } from "@/shared/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/shared/components/ui/table";
import { Badge } from "@/shared/components/ui/badge";

import PaginationCustom from "@/shared/components/common/Panigation";
import UploadPredictBox from "@/shared/components/common/UploadPredictBox";
import { useGetLegacyJobsByUserIdQuery } from "@/core/api/jobApi";
import { Activity, CheckCircle2, Clock3, Gauge, Search, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useAppSettings } from "@/shared/hooks/useAppSettings";

const formatDate = (timestamp: number | undefined, locale: string, fallback: string): string => {
  if (!timestamp) return fallback;
  const date = new Date(timestamp * 1000);
  return date.toLocaleString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const isCompleted = (status: number | string) => Number(status) === 1;
const isRunning = (status: number | string) => Number(status) === 0;

const TrainingHistory = () => {
  const locale = useLocale();
  const t = useTranslations("TrainingHistory");
  const common = useTranslations("Common");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "done" | "running" | "error">("all");

  const { data: session } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [effectiveHighlight, setEffectiveHighlight] = useState<string | null>(null);
  const [focusedJobId, setFocusedJobId] = useState<string | null>(null);
  const [flashJobId, setFlashJobId] = useState<string | null>(null);
  const userId = session?.user?.id;
  const { data: jobs = [], isLoading, refetch } = useGetLegacyJobsByUserIdQuery(
    userId ?? "",
    { skip: !userId },
  );

  // Đọc target highlight từ URL hoặc sessionStorage
  useEffect(() => {
    const fromUrl = searchParams?.get("highlight") || searchParams?.get("job_id");
    const fromSession =
      typeof window !== "undefined"
        ? sessionStorage.getItem("latest_training_job_id")
        : null;

    const target = fromUrl || fromSession;
    if (target) {
      setEffectiveHighlight(target);
    }
  }, [searchParams]);

  // Luôn refetch khi có target highlight hoặc khi vào trang để lấy job mới nhất từ backend
  useEffect(() => {
    if (userId) {
      refetch();
    }
  }, [userId, effectiveHighlight, refetch]);

  const { settings } = useAppSettings();
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = settings.tablePageSize || 10;

  const [openRow, setOpenRow] = useState<string | null>(null);
  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";

  const filteredJobs = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return [...jobs]
      .filter((job) => {
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "done" && isCompleted(job.status)) ||
          (statusFilter === "running" && isRunning(job.status)) ||
          (statusFilter === "error" && !isCompleted(job.status) && !isRunning(job.status));
        const searchable = [
          job.data?.name,
          job.best_model,
          job.config?.problem_type,
          job.config?.target,
          job.job_id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        const matchesSearch = !keyword || searchable.includes(keyword);

        return matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        const timeA = a.create_at || 0;
        const timeB = b.create_at || 0;
        return sortAsc ? timeA - timeB : timeB - timeA;
      });
  }, [jobs, search, sortAsc, statusFilter]);

  const completedCount = jobs.filter((job) => isCompleted(job.status)).length;
  const runningCount = jobs.filter((job) => isRunning(job.status)).length;
  const errorCount = jobs.filter(
    (job) => !isCompleted(job.status) && !isRunning(job.status),
  ).length;
  const bestScore = jobs
    .filter((job) => isCompleted(job.status) && job.best_score !== undefined)
    .reduce((best, job) => Math.max(best, job.best_score || 0), 0);

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / itemsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * itemsPerPage;
  const currentJobs = filteredJobs.slice(startIndex, startIndex + itemsPerPage);

  // Cuộn và focus vào đúng dòng của Job được chỉ định
  useEffect(() => {
    if (!effectiveHighlight || filteredJobs.length === 0) return;

    const matchedIndex = filteredJobs.findIndex(
      (j) =>
        j.job_id === effectiveHighlight ||
        j._id === effectiveHighlight ||
        String(j.job_id).toLowerCase().includes(effectiveHighlight.toLowerCase()),
    );

    // Nếu không tìm thấy trong danh sách đã filter, có thể do đang bị lọc status hoặc search -> reset filter
    if (matchedIndex === -1) {
      if (statusFilter !== "all" || search !== "") {
        setStatusFilter("all");
        setSearch("");
      }
      return;
    }

    const targetJob = filteredJobs[matchedIndex];
    const targetPage = Math.floor(matchedIndex / itemsPerPage) + 1;

    if (currentPage !== targetPage) {
      setCurrentPage(targetPage);
    }

    setFocusedJobId(targetJob.job_id);
    setFlashJobId(targetJob.job_id);

    const timer = setTimeout(() => {
      const el = document.getElementById(`job-row-${targetJob.job_id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.focus();
      }
    }, 220);

    const flashTimer = setTimeout(() => {
      setFlashJobId(null);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("latest_training_job_id");
      }
    }, 3500);

    return () => {
      clearTimeout(timer);
      clearTimeout(flashTimer);
    };
  }, [
    effectiveHighlight,
    filteredJobs,
    itemsPerPage,
    currentPage,
    statusFilter,
    search,
  ]);

  return (
    <div className="space-y-6">
      <DataWorkspaceHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        subtitle={t("subtitle")}
      />

      <DataWorkspaceMetrics
        metrics={[
          {
            label: t("metrics.totalRuns"),
            value: `${jobs.length}`,
            detail: t("metrics.createdPipelines"),
            icon: Activity,
            tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
          },
          {
            label: t("metrics.completed"),
            value: `${completedCount}`,
            detail: t("metrics.canViewResults"),
            icon: CheckCircle2,
            tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
          },
          {
            label: t("metrics.running"),
            value: `${runningCount}`,
            detail: t("metrics.processingData"),
            icon: Clock3,
            tone: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
          },
          {
            label: t("metrics.bestScore"),
            value: bestScore ? `${(bestScore * 100).toFixed(1)}%` : "--",
            detail: t("metrics.needsReview", { count: errorCount }),
            icon: Gauge,
            tone: "bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-400",
          },
        ]}
      />

      <DataWorkspaceControls
        summary={t("summary", { shown: filteredJobs.length, total: jobs.length })}
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
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as "all" | "done" | "running" | "error")
          }
          className={`${workspaceInputClass} sm:w-52`}
        >
          <option value="all">{t("filters.all")}</option>
          <option value="done">{t("filters.done")}</option>
          <option value="running">{t("filters.running")}</option>
          <option value="error">{t("filters.error")}</option>
        </select>
        <button
          className="automl-data-chip automl-data-chip-secondary h-11 rounded-2xl px-4"
          onClick={() => setSortAsc((value) => !value)}
          type="button"
        >
          {t("sortByDate", { order: sortAsc ? t("oldest") : t("newest") })}
        </button>
      </DataWorkspaceControls>

      <Card className="automl-data-card w-full">
        <CardContent className="automl-table-wrap pt-5">
        {isLoading ? (
          <AppLoading label={common("loadingData")} />
        ) : filteredJobs.length === 0 ? (
          <div className="automl-state-panel">{t("empty")}</div>
        ) : (
          <>
            <Table className="automl-data-table">
              <TableHeader>
                <TableRow>
                  <TableHead>{t("table.dataset")}</TableHead>
                  <TableHead>{t("table.bestModel")}</TableHead>
                  <TableHead>{t("table.accuracy")}</TableHead>
                  <TableHead>{t("table.trainingDate")}</TableHead>
                  <TableHead className="text-center">{t("table.status")}</TableHead>
                  <TableHead className="text-center">{common("actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentJobs.map((job) => (
                  <React.Fragment key={job._id}>
                    <TableRow
                      id={`job-row-${job.job_id}`}
                      tabIndex={0}
                      onClick={() => setFocusedJobId(job.job_id)}
                      onFocus={() => setFocusedJobId(job.job_id)}
                      className={cn(
                        "cursor-pointer transition-all outline-none",
                        focusedJobId === job.job_id &&
                          "automl-row-focused bg-blue-50/70 dark:bg-blue-950/40 ring-2 ring-blue-500/50 shadow-xs",
                        flashJobId === job.job_id &&
                          "automl-row-flash ring-2 ring-blue-600 bg-blue-100/70 dark:bg-blue-900/50 shadow-md",
                      )}
                      data-focused={focusedJobId === job.job_id}
                    >
                      <TableCell className="font-bold text-[var(--automl-data-text)]">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-automl-blue-soft text-[11px] font-black text-automl-blue">
                            {(job.data?.name || "TR").slice(0, 2).toUpperCase()}
                          </span>
                          <span className="min-w-0 truncate">
                            {job.data?.name || common("unknown")}
                          </span>
                        </div>
                      </TableCell>

                      <TableCell>
                        {isCompleted(job.status)
                          ? job.best_model || common("unknown")
                          : t("processing")}
                      </TableCell>

                      <TableCell>
                        {isCompleted(job.status) && job.best_score !== undefined
                          ? (
                            <div className="min-w-28 max-w-36">
                              <div className="mb-1 flex items-center justify-between gap-2 text-xs font-bold">
                                <span>{(job.best_score * 100).toFixed(1)}%</span>
                              </div>
                              <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10">
                                <div
                                  className="h-1.5 rounded-full bg-automl-blue transition-all"
                                  style={{ width: `${Math.min(job.best_score * 100, 100)}%` }}
                                />
                              </div>
                            </div>
                          )
                          : t("processing")}
                      </TableCell>

                      <TableCell>{formatDate(job.create_at, dateLocale, common("noData"))}</TableCell>

                      <TableCell className="text-center">
                        {isCompleted(job.status) ? (
                          <Badge variant="outline" className="automl-status-success rounded-full px-2.5 py-0.5 text-xs font-bold">
                            {t("status.completed")}
                          </Badge>
                        ) : isRunning(job.status) ? (
                          <Badge variant="secondary" className="automl-status-warning rounded-full px-2.5 py-0.5 text-xs font-bold">
                            {t("status.training")}
                          </Badge>
                        ) : (
                          <Badge variant="default" className="automl-status-error rounded-full px-2.5 py-0.5 text-xs font-bold">
                            <XCircle className="mr-1 h-3 w-3" />
                            {t("status.error")}
                          </Badge>
                        )}
                      </TableCell>

                      <TableCell className="text-center">
                        <div className="flex justify-center">
                          <RowActionMenu
                            label={t("openActions", { name: job.data?.name || "training run" })}
                            items={[
                              {
                                label: t("actions.viewDetails"),
                                disabled: !isCompleted(job.status),
                                onClick: () => router.push(`/training-history/${job.job_id}`),
                              },
                              {
                                label: openRow === job.job_id ? t("actions.closeUpload") : t("actions.uploadTest"),
                                onClick: () =>
                                  setOpenRow(
                                    openRow === job.job_id ? null : job.job_id,
                                  ),
                              },
                            ]}
                          />
                        </div>
                      </TableCell>
                    </TableRow>

                    {openRow === job.job_id && (
                      <TableRow>
                        <TableCell colSpan={6}>
                          <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4 animate-in fade-in slide-in-from-top-2">
                            <UploadPredictBox
                              jobId={job.job_id}
                              disabled={!isCompleted(job.status)}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>

            <PaginationCustom
              currentPage={safeCurrentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          </>
        )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TrainingHistory;
