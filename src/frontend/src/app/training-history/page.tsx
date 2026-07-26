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
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

import PaginationCustom from "@/components/common/Panigation";
import UploadPredictBox from "@/components/common/UploadPredictBox";
import { useGetLegacyJobsByUserIdQuery } from "@/redux/api/jobApi";
import { Activity, CheckCircle2, Clock3, Gauge, Search, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

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
  const userId = session?.user?.id;
  const { data: jobs = [], isLoading } = useGetLegacyJobsByUserIdQuery(
    userId ?? "",
    { skip: !userId },
  );

  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 5;

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
            tone: "from-blue-100 to-sky-100 text-blue-600",
          },
          {
            label: t("metrics.completed"),
            value: `${completedCount}`,
            detail: t("metrics.canViewResults"),
            icon: CheckCircle2,
            tone: "from-emerald-100 to-teal-100 text-emerald-600",
          },
          {
            label: t("metrics.running"),
            value: `${runningCount}`,
            detail: t("metrics.processingData"),
            icon: Clock3,
            tone: "from-amber-100 to-orange-100 text-amber-600",
          },
          {
            label: t("metrics.bestScore"),
            value: bestScore ? `${(bestScore * 100).toFixed(1)}%` : "--",
            detail: t("metrics.needsReview", { count: errorCount }),
            icon: Gauge,
            tone: "from-violet-100 to-indigo-100 text-violet-600",
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
                    <TableRow className={isCompleted(job.status) ? "automl-row-highlight" : undefined}>
                      <TableCell className="font-bold text-[var(--automl-data-text)]">
                        <div className="flex items-center gap-3">
                          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-xs font-black text-automl-blue">
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
                            <div className="min-w-32">
                              <div className="mb-2 flex items-center justify-between gap-3">
                                <span>{(job.best_score * 100).toFixed(2)}%</span>
                              </div>
                              <div className="h-2 rounded-full bg-slate-100 dark:bg-white/10">
                                <div
                                  className="h-2 rounded-full bg-automl-blue"
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
                          <Badge variant="outline" className="automl-status-success rounded-full px-3 py-1">
                            {t("status.completed")}
                          </Badge>
                        ) : isRunning(job.status) ? (
                          <Badge variant="secondary" className="automl-status-warning rounded-full px-3 py-1">
                            {t("status.training")}
                          </Badge>
                        ) : (
                          <Badge variant="default" className="automl-status-error rounded-full px-3 py-1">
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
