"use client";

import RowActionMenu from "@/shared/components/common/RowActionMenu";
import AppLoading from "@/shared/components/common/AppLoading";
import {
  DataWorkspaceControls,
  DataWorkspaceHeader,
  DataWorkspaceMetrics,
  workspaceInputClass,
} from "@/shared/components/common/DataWorkspace";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
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
import { useGetLegacyJobsByUserIdQuery } from "@/core/api/jobApi";
import { useActivateModelMutation } from "@/core/api/inferenceApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { CheckCircle2, Clock3, Gauge, Search, ServerCog } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useAppSettings } from "@/shared/hooks/useAppSettings";

const formatDate = (timestamp: number | undefined, locale: string, fallback: string) => {
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

const ImplementProject = () => {
  const locale = useLocale();
  const t = useTranslations("Deploy");
  const common = useTranslations("Common");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [focusedJobId, setFocusedJobId] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "ready" | "training">("all");

  const { data: session } = useSession();
  const router = useRouter();
  const userId = session?.user?.id;
  const { data: jobs = [], isLoading } = useGetLegacyJobsByUserIdQuery(
    userId ?? "",
    { skip: !userId },
  );
  const [activateModel] = useActivateModelMutation();
  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";

  const { settings } = useAppSettings();
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = settings.tablePageSize || 10;

  const handleConfirm = async () => {
    if (!selectedJobId) return;
    try {
      await activateModel({ jobId: selectedJobId, activate: 1 }).unwrap();

      router.push(`/implement-project/${selectedJobId}`);
    } catch (err) {
      console.error("Activate model error:", err);
      alert(getApiErrorMessage(err, t("activateFailed")));
    } finally {
      setSelectedJobId(null);
    }
  };

  const filteredJobs = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return [...jobs]
      .filter((job) => {
        const done = isCompleted(job.status);
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "ready" && done) ||
          (statusFilter === "training" && !done);
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
        if (!a.create_at || !b.create_at) return 0;
        return sortOrder === "asc"
          ? a.create_at - b.create_at
          : b.create_at - a.create_at;
      });
  }, [jobs, search, sortOrder, statusFilter]);

  const readyCount = jobs.filter((job) => isCompleted(job.status)).length;
  const trainingCount = jobs.length - readyCount;
  const bestScore = jobs
    .filter((job) => isCompleted(job.status) && job.best_score !== undefined)
    .reduce((best, job) => Math.max(best, job.best_score || 0), 0);

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / itemsPerPage));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedJobs = filteredJobs.slice(
    (safeCurrentPage - 1) * itemsPerPage,
    safeCurrentPage * itemsPerPage,
  );

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
            label: t("metrics.totalModels"),
            value: `${jobs.length}`,
            detail: t("metrics.fromHistory"),
            icon: ServerCog,
            tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
          },
          {
            label: t("metrics.eligible"),
            value: `${readyCount}`,
            detail: t("metrics.deployable"),
            icon: CheckCircle2,
            tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
          },
          {
            label: t("metrics.processing"),
            value: `${trainingCount}`,
            detail: t("metrics.noEndpoint"),
            icon: Clock3,
            tone: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
          },
          {
            label: t("metrics.bestAccuracy"),
            value: bestScore ? `${(bestScore * 100).toFixed(1)}%` : "--",
            detail: t("metrics.deploymentCandidate"),
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
            setStatusFilter(event.target.value as "all" | "ready" | "training")
          }
          className={`${workspaceInputClass} sm:w-52`}
        >
          <option value="all">{t("filters.all")}</option>
          <option value="ready">{t("filters.ready")}</option>
          <option value="training">{t("filters.training")}</option>
        </select>
        <button
          className="automl-data-chip automl-data-chip-secondary h-11 rounded-2xl px-4"
          onClick={() =>
            setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))
          }
          type="button"
        >
          {t("sortByDate", { order: sortOrder === "asc" ? t("oldest") : t("newest") })}
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
                  <TableHead>{t("table.status")}</TableHead>
                  <TableHead className="text-center">{common("actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedJobs.map((job) => {
                  const isDone = isCompleted(job.status);
                  const isSelected = selectedJobId === job.job_id;
                  const readiness = isDone ? 100 : 42;

                  return (
                    <TableRow
                      key={job._id}
                      id={`implement-row-${job.job_id}`}
                      tabIndex={0}
                      onClick={() => setFocusedJobId(job.job_id)}
                      onFocus={() => setFocusedJobId(job.job_id)}
                      className={cn(
                        "cursor-pointer transition-all outline-none",
                        focusedJobId === job.job_id && "automl-row-focused",
                      )}
                      data-focused={focusedJobId === job.job_id}
                    >
                      <TableCell className="font-bold text-[var(--automl-data-text)]">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-automl-blue-soft text-[11px] font-black text-automl-blue">
                            {(job.data?.name || "MD").slice(0, 2).toUpperCase()}
                          </span>
                          <span className="min-w-0 truncate">
                            {job.data?.name || common("unknown")}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {isDone ? job.best_model || common("unknown") : t("processing")}
                      </TableCell>
                      <TableCell>
                        {isDone && job.best_score !== undefined
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
                      <TableCell>
                        <div className="space-y-1.5">
                          <Badge
                            variant="outline"
                            className={`${isDone ? "automl-status-success" : "automl-status-warning"} rounded-full px-2.5 py-0.5 text-xs font-bold`}
                          >
                            {isDone ? t("status.ready") : t("status.training")}
                          </Badge>
                          <div className="h-1.5 w-24 rounded-full bg-slate-100 dark:bg-white/10">
                            <div
                              className="h-1.5 rounded-full bg-automl-blue transition-all"
                              style={{ width: `${readiness}%` }}
                            />
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex justify-center">
                          <RowActionMenu
                            label={t("openActions", { name: job.data?.name || "model" })}
                            items={[
                              {
                                label: t("actions.deploy"),
                                disabled: !isDone,
                                onClick: () => setSelectedJobId(job.job_id),
                              },
                              {
                                label: t("actions.viewHistory"),
                                onClick: () => router.push(`/training-history/${job.job_id}`),
                              },
                            ]}
                          />
                        </div>
                        <AlertDialog
                          open={isSelected}
                          onOpenChange={(open) =>
                            !open && setSelectedJobId(null)
                          }
                        >
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                {t("confirm.title")}
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                {t("confirm.description")}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
                              <AlertDialogAction onClick={handleConfirm}>
                                {common("confirm")}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </TableCell>
                    </TableRow>
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
    </div>
  );
};

export default ImplementProject;
