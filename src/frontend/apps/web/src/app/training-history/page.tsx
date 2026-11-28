"use client";

import Link from "next/link";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";

import PaginationCustom from "@/shared/components/common/Panigation";
import UploadPredictBox from "@/shared/components/common/UploadPredictBox";
import {
  useCancelTrainingJobMutation,
  useGetJobsQuery,
  type TrainingJob,
} from "@/core/api/jobApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import {
  isJobActive,
  isJobCancelled,
  isJobCompleted,
  isJobQueued,
  isJobRunning,
} from "@/features/training/utils/pipelineGraphBuilder";
import {
  Activity,
  Ban,
  CheckCircle2,
  Clock3,
  Gauge,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useAppSettings } from "@/shared/hooks/useAppSettings";
import { useToast } from "@/shared/hooks/use-toast";

const NON_PERCENT_METRICS = new Set(["mse", "mae", "mape", "rmse", "r2", "log_loss", "loss"]);

const formatDate = (
  timestamp: number | string | undefined,
  locale: string,
  fallback: string,
): string => {
  if (!timestamp) return fallback;
  const date =
    typeof timestamp === "number"
      ? new Date(timestamp > 1e12 ? timestamp : timestamp * 1000)
      : new Date(timestamp);
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getJobTimestamp = (job: TrainingJob): number => {
  if (typeof job.create_at === "number") return job.create_at;
  if (typeof job.created_at === "number") return job.created_at;
  if (typeof job.created_at === "string") {
    const parsed = Date.parse(job.created_at);
    return Number.isNaN(parsed) ? 0 : Math.floor(parsed / 1000);
  }
  return 0;
};

const isPercentMetric = (job: TrainingJob): boolean => {
  const score = job.best_score;
  if (score === undefined || score === null) return false;
  if (score < 0 || score > 1) return false;
  const metric = (job.config?.metric_sort || "").trim().toLowerCase();
  if (NON_PERCENT_METRICS.has(metric)) return false;
  const problem = (job.config?.problem_type || "").trim().toLowerCase();
  if (problem === "regression") return false;
  return true;
};

const formatScoreDisplay = (job: TrainingJob): string => {
  if (job.best_score === undefined || job.best_score === null) return "--";
  if (isPercentMetric(job)) {
    return `${(job.best_score * 100).toFixed(1)}%`;
  }
  return Number.isInteger(job.best_score)
    ? job.best_score.toLocaleString("en-US")
    : job.best_score.toFixed(4);
};

const TrainingHistory = () => {
  const locale = useLocale();
  const t = useTranslations("TrainingHistory");
  const common = useTranslations("Common");
  const { toast } = useToast();

  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "done" | "running" | "error">("all");
  const [cancelTargetJobId, setCancelTargetJobId] = useState<string | null>(null);

  const { data: session } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [effectiveHighlight, setEffectiveHighlight] = useState<string | null>(null);
  const [focusedJobId, setFocusedJobId] = useState<string | null>(null);
  const [flashJobId, setFlashJobId] = useState<string | null>(null);

  const {
    data: jobsResponse,
    isLoading,
    isFetching,
    refetch,
  } = useGetJobsQuery(
    {
      current_page: 1,
      page_size: 100,
      sort_time: sortAsc ? "asc" : "desc",
    },
    { skip: !session?.user },
  );

  const [cancelTrainingJob, { isLoading: isCancelling }] = useCancelTrainingJobMutation();

  const jobs: TrainingJob[] = useMemo(() => {
    if (Array.isArray(jobsResponse)) return jobsResponse as TrainingJob[];
    return jobsResponse?.data || [];
  }, [jobsResponse]);

  // Read highlight target from URL or sessionStorage
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

  // Refetch on mount or when highlight target updates to get latest backend state
  useEffect(() => {
    if (session?.user) {
      refetch();
    }
  }, [session?.user, effectiveHighlight, refetch]);

  const { settings } = useAppSettings();
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = settings.tablePageSize || 10;

  const [openRow, setOpenRow] = useState<string | null>(null);
  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";

  const handleConfirmCancelJob = async () => {
    if (!cancelTargetJobId) return;
    try {
      await cancelTrainingJob(cancelTargetJobId).unwrap();
      toast({
        title: t("cancel.successTitle"),
        description: t("cancel.successDesc"),
      });
      refetch();
    } catch (err) {
      toast({
        title: t("cancel.errorTitle"),
        description: getApiErrorMessage(err, t("cancel.errorDesc")),
        variant: "destructive",
      });
    } finally {
      setCancelTargetJobId(null);
    }
  };

  const filteredJobs = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return [...jobs]
      .filter((job) => {
        const done = isJobCompleted(job.status);
        const active = isJobActive(job.status);
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "done" && done) ||
          (statusFilter === "running" && active) ||
          (statusFilter === "error" && !done && !active);
        const searchable = [
          job.data?.name,
          job.best_model,
          job.config?.problem_type,
          job.config?.target,
          job.job_id,
          job._id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        const matchesSearch = !keyword || searchable.includes(keyword);

        return matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        const timeA = getJobTimestamp(a);
        const timeB = getJobTimestamp(b);
        return sortAsc ? timeA - timeB : timeB - timeA;
      });
  }, [jobs, search, sortAsc, statusFilter]);

  const completedCount = jobs.filter((job) => isJobCompleted(job.status)).length;
  const runningCount = jobs.filter((job) => isJobActive(job.status)).length;
  const errorCount = jobs.filter(
    (job) => !isJobCompleted(job.status) && !isJobActive(job.status),
  ).length;
  const bestPercentJob = jobs
    .filter((job) => isJobCompleted(job.status) && isPercentMetric(job))
    .reduce<TrainingJob | null>((best, job) => {
      if (!best) return job;
      return (job.best_score ?? 0) > (best.best_score ?? 0) ? job : best;
    }, null);

  const bestFallbackJob = !bestPercentJob
    ? jobs.find((job) => isJobCompleted(job.status) && job.best_score !== undefined)
    : null;

  const bestScoreDisplay = bestPercentJob
    ? formatScoreDisplay(bestPercentJob)
    : bestFallbackJob
      ? formatScoreDisplay(bestFallbackJob)
      : "--";

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / itemsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const startIndex = (safeCurrentPage - 1) * itemsPerPage;
  const currentJobs = filteredJobs.slice(startIndex, startIndex + itemsPerPage);

  // Scroll & focus to highlighted job row
  useEffect(() => {
    if (!effectiveHighlight || filteredJobs.length === 0) return;

    const matchedIndex = filteredJobs.findIndex(
      (j) =>
        j.job_id === effectiveHighlight ||
        j._id === effectiveHighlight ||
        String(j.job_id || j._id)
          .toLowerCase()
          .includes(effectiveHighlight.toLowerCase()),
    );

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

    const targetJobId = targetJob.job_id || targetJob._id;
    setFocusedJobId(targetJobId);
    setFlashJobId(targetJobId);

    const timer = setTimeout(() => {
      const el = document.getElementById(`job-row-${targetJobId}`);
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
            value: bestScoreDisplay,
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
        <button
          className="automl-data-chip automl-data-chip-secondary inline-flex h-11 items-center gap-1.5 rounded-2xl px-4"
          onClick={() => refetch()}
          disabled={isFetching}
          type="button"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
          {t("actions.refresh")}
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
                  {currentJobs.map((job) => {
                    const jobId = job.job_id || job._id;
                    const completed = isJobCompleted(job.status);
                    const running = isJobRunning(job.status);
                    const queued = isJobQueued(job.status);
                    const active = isJobActive(job.status);
                    const cancelled = isJobCancelled(job.status);
                    const percentMetric = isPercentMetric(job);

                    const actionItems = [
                      {
                        label: active ? t("actions.trackProgress") : t("actions.viewDetails"),
                        onClick: () => router.push(`/training-history/${jobId}`),
                      },
                      ...(active
                        ? [
                            {
                              label: t("actions.cancelJob"),
                              onClick: () => setCancelTargetJobId(jobId),
                            },
                          ]
                        : []),
                      {
                        label: openRow === jobId ? t("actions.closeUpload") : t("actions.uploadTest"),
                        disabled: !completed,
                        onClick: () => setOpenRow(openRow === jobId ? null : jobId),
                      },
                    ];

                    return (
                      <React.Fragment key={job._id || jobId}>
                        <TableRow
                          id={`job-row-${jobId}`}
                          tabIndex={0}
                          onClick={() => setFocusedJobId(jobId)}
                          onFocus={() => setFocusedJobId(jobId)}
                          className={cn(
                            "cursor-pointer transition-all outline-none",
                            focusedJobId === jobId &&
                              "automl-row-focused bg-blue-50/70 dark:bg-blue-950/40 ring-2 ring-blue-500/50 shadow-xs",
                            flashJobId === jobId &&
                              "automl-row-flash ring-2 ring-blue-600 bg-blue-100/70 dark:bg-blue-900/50 shadow-md",
                          )}
                          data-focused={focusedJobId === jobId}
                        >
                          <TableCell className="font-bold text-[var(--automl-data-text)]">
                            <Link
                              href={`/training-history/${jobId}`}
                              onClick={(e) => e.stopPropagation()}
                              className="group flex items-center gap-2.5 hover:text-automl-blue transition-colors"
                            >
                              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-automl-blue-soft text-[11px] font-black text-automl-blue">
                                {(job.data?.name || "TR").slice(0, 2).toUpperCase()}
                              </span>
                              <span className="min-w-0 truncate group-hover:underline">
                                {job.data?.name || common("unknown")}
                              </span>
                            </Link>
                          </TableCell>

                          <TableCell>
                            {completed
                              ? job.best_model || common("unknown")
                              : active
                                ? t("processing")
                                : job.best_model || "—"}
                          </TableCell>

                          <TableCell>
                            {completed && job.best_score !== undefined && job.best_score !== null ? (
                              percentMetric ? (
                                <div className="min-w-28 max-w-36">
                                  <div className="mb-1 flex items-center justify-between gap-2 text-xs font-bold">
                                    <span>{formatScoreDisplay(job)}</span>
                                  </div>
                                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10">
                                    <div
                                      className="h-1.5 rounded-full bg-automl-blue transition-all"
                                      style={{ width: `${Math.min(Math.max(job.best_score * 100, 0), 100)}%` }}
                                    />
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center gap-1.5 font-mono text-xs font-bold">
                                  <span>{formatScoreDisplay(job)}</span>
                                  {job.config?.metric_sort && (
                                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-500 dark:bg-white/10 dark:text-slate-300">
                                      {job.config.metric_sort}
                                    </span>
                                  )}
                                </div>
                              )
                            ) : active ? (
                              t("processing")
                            ) : (
                              "—"
                            )}
                          </TableCell>

                          <TableCell>
                            {formatDate(job.create_at ?? job.created_at, dateLocale, common("noData"))}
                          </TableCell>

                          <TableCell className="text-center">
                            {completed ? (
                              <Badge variant="outline" className="automl-status-success rounded-full px-2.5 py-0.5 text-xs font-bold">
                                {t("status.completed")}
                              </Badge>
                            ) : running ? (
                              <Badge variant="secondary" className="automl-status-warning rounded-full px-2.5 py-0.5 text-xs font-bold">
                                <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                                {t("status.training")}
                              </Badge>
                            ) : queued ? (
                              <Badge variant="outline" className="rounded-full border-blue-300 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300">
                                {t("status.queued")}
                              </Badge>
                            ) : cancelled ? (
                              <Badge variant="outline" className="rounded-full border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                <Ban className="mr-1 h-3 w-3" />
                                {t("status.cancelled")}
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
                                items={actionItems}
                              />
                            </div>
                          </TableCell>
                        </TableRow>

                        {openRow === jobId && (
                          <TableRow>
                            <TableCell colSpan={6}>
                              <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4 animate-in fade-in slide-in-from-top-2">
                                <UploadPredictBox
                                  jobId={jobId}
                                  disabled={!completed}
                                />
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    );
                  })}
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

      <AlertDialog
        open={Boolean(cancelTargetJobId)}
        onOpenChange={(open) => !open && setCancelTargetJobId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("cancel.title")}</AlertDialogTitle>
            <AlertDialogDescription>{t("cancel.description")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isCancelling}>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmCancelJob}
              disabled={isCancelling}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {common("confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default TrainingHistory;
