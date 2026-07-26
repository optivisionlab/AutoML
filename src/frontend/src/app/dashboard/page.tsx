"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSession } from "next-auth/react";
import {
  Activity,
  CalendarCheck,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  Rocket,
  TrendingUp,
} from "lucide-react";
import AppLoading from "@/components/common/AppLoading";
import {
  Dataset,
  useGetAllUserDatasetsQuery,
  useGetDatasetsByUserIdQuery,
} from "@/redux/api/datasetApi";
import {
  TrainingJob,
  useGetLegacyJobsByUserIdQuery,
} from "@/redux/api/jobApi";
import { cn } from "@/lib/utils";
import { useLocale, useTranslations } from "next-intl";

const MONTH_LABELS = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  vi: ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12"],
};
const CATEGORY_COLORS = ["#3b82f6", "#8b5cf6", "#2dd4bf", "#cbd5e1", "#c4b5fd"];

const formatDate = (timestamp: number | undefined, locale: string, fallback: string) => {
  if (!timestamp) return fallback;

  return new Date(timestamp * 1000).toLocaleDateString(locale);
};

const formatPercent = (value?: number) =>
  value === undefined ? "--" : `${(value * 100).toFixed(1)}%`;

const isCompleted = (status: number | string) => Number(status) === 1;
const isRunning = (status: number | string) => Number(status) === 0;

const getDatasetTime = (dataset: Dataset) =>
  dataset.latestUpdate || dataset.lastestUpdate || dataset.createDate || 0;

const getJobTime = (job: TrainingJob) => job.create_at || 0;

const buildConicGradient = (
  categories: Array<{ label: string; count: number; percent: number }>,
) => {
  if (categories.length === 0) return "#e2e8f0";

  let cursor = 0;
  const stops = categories.map((category, index) => {
    const start = cursor;
    const end = index === categories.length - 1 ? 100 : cursor + category.percent;
    cursor = end;
    return `${CATEGORY_COLORS[index % CATEGORY_COLORS.length]} ${start}% ${end}%`;
  });

  return `conic-gradient(${stops.join(",")})`;
};

export default function DashboardPage() {
  const locale = useLocale();
  const t = useTranslations("Dashboard");
  const common = useTranslations("Common");
  const { data: session, status } = useSession();
  const userId = session?.user?.id;
  const isAdmin = session?.user?.role === "admin";

  const { data: publicDatasets = [], isLoading: isPublicLoading } =
    useGetDatasetsByUserIdQuery("0");
  const { data: personalDatasets = [], isLoading: isPersonalLoading } =
    useGetDatasetsByUserIdQuery(userId ?? "", {
      skip: !userId || isAdmin,
    });
  const { data: adminDatasets = [], isLoading: isAdminDatasetsLoading } =
    useGetAllUserDatasetsQuery(undefined, {
      skip: !isAdmin,
    });
  const { data: jobs = [], isLoading: isJobsLoading } =
    useGetLegacyJobsByUserIdQuery(userId ?? "", {
      skip: !userId,
    });

  const ownedDatasets = isAdmin ? adminDatasets : personalDatasets;
  const allDatasets = useMemo(
    () => [...ownedDatasets, ...publicDatasets],
    [ownedDatasets, publicDatasets],
  );

  const dateLocale = locale === "vi" ? "vi-VN" : "en-US";
  const monthLabels = locale === "vi" ? MONTH_LABELS.vi : MONTH_LABELS.en;

  const getRelativeTime = (timestamp?: number) => {
    if (!timestamp) return t("time.unknown");

    const diffMinutes = Math.max(
      0,
      Math.floor((Date.now() - timestamp * 1000) / 60000),
    );

    if (diffMinutes < 1) return t("time.justNow");
    if (diffMinutes < 60) return t("time.minutesAgo", { count: diffMinutes });

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return t("time.hoursAgo", { count: diffHours });

    const diffDays = Math.floor(diffHours / 24);
    return t("time.daysAgo", { count: diffDays });
  };

  const dashboard = useMemo(() => {
    const now = Date.now();
    const thirtyDaysAgo = now - 30 * 24 * 60 * 60 * 1000;
    const currentYear = new Date().getFullYear();
    const completedJobs = jobs.filter((job) => isCompleted(job.status));
    const runningJobs = jobs.filter((job) => isRunning(job.status));
    const deployReadyJobs = completedJobs.filter((job) => job.best_model);
    const bestJob = completedJobs.reduce<TrainingJob | undefined>(
      (best, job) =>
        (job.best_score || 0) > (best?.best_score || 0) ? job : best,
      undefined,
    );
    const recentDatasets = allDatasets.filter(
      (dataset) => getDatasetTime(dataset) * 1000 >= thirtyDaysAgo,
    );
    const recentJobs = [...jobs].sort((a, b) => getJobTime(b) - getJobTime(a));
    const monthCounts = Array.from({ length: 12 }, () => 0);

    jobs.forEach((job) => {
      if (!job.create_at) return;

      const date = new Date(job.create_at * 1000);
      if (date.getFullYear() === currentYear) {
        monthCounts[date.getMonth()] += 1;
      }
    });

    const maxMonthCount = Math.max(...monthCounts, 1);
    const categoryMap = new Map<string, number>();

    jobs.forEach((job) => {
      const label = job.config?.problem_type || t("uncategorized");
      categoryMap.set(label, (categoryMap.get(label) || 0) + 1);
    });

    if (categoryMap.size === 0) {
      allDatasets.forEach((dataset) => {
        const label = dataset.dataType || t("uncategorized");
        categoryMap.set(label, (categoryMap.get(label) || 0) + 1);
      });
    }

    const categoryTotal = Array.from(categoryMap.values()).reduce(
      (sum, value) => sum + value,
      0,
    );
    const categories = Array.from(categoryMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([label, count]) => ({
        label,
        count,
        percent: categoryTotal ? Math.round((count / categoryTotal) * 100) : 0,
      }));

    const activities = [
      ...allDatasets.map((dataset) => ({
        id: `dataset-${dataset._id}`,
        title: t("activity.datasetUpdated"),
        body: dataset.dataName || common("unnamed"),
        timestamp: getDatasetTime(dataset),
        href: isAdmin ? "/admin/datasets/users" : "/my-datasets",
        icon: Database,
      })),
      ...jobs.map((job) => ({
        id: `job-${job.job_id}`,
        title: isCompleted(job.status)
          ? t("activity.trainingCompleted")
          : isRunning(job.status)
            ? t("activity.pipelineRunning")
            : t("activity.trainingNeedsReview"),
        body: `${job.data?.name || common("unknown")}${
          job.best_score !== undefined ? ` · ${formatPercent(job.best_score)}` : ""
        }`,
        timestamp: getJobTime(job),
        href: isCompleted(job.status)
          ? `/training-history/${job.job_id}`
          : "/training-history",
        icon: isCompleted(job.status)
          ? CheckCircle2
          : isRunning(job.status)
            ? Activity
            : Clock3,
      })),
    ]
      .filter((activity) => activity.timestamp)
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 5);

    return {
      completedJobs,
      runningJobs,
      deployReadyJobs,
      bestJob,
      recentDatasets,
      recentJobs: recentJobs.slice(0, 5),
      monthCounts,
      maxMonthCount,
      categories,
      activities,
    };
  }, [allDatasets, common, isAdmin, jobs, t]);

  const datasetHref = isAdmin ? "/admin/datasets/users" : "/my-datasets";
  const isLoading =
    status === "loading" ||
    isPublicLoading ||
    isPersonalLoading ||
    isAdminDatasetsLoading ||
    isJobsLoading;

  const metrics = [
    {
      label: t("metrics.totalDatasets"),
      value: `${allDatasets.length}`,
      change: t("metrics.newCount", { count: dashboard.recentDatasets.length }),
      detail: t("metrics.last30Days"),
      icon: Database,
      tone: "from-blue-100 to-sky-100 text-blue-600",
      href: datasetHref,
    },
    {
      label: t("metrics.trainingRuns"),
      value: `${jobs.length}`,
      change: t("metrics.runningCount", { count: dashboard.runningJobs.length }),
      detail: t("metrics.accountPipelines"),
      icon: CalendarCheck,
      tone: "from-violet-100 to-indigo-100 text-violet-600",
      href: "/training-history",
    },
    {
      label: t("metrics.bestAccuracy"),
      value: formatPercent(dashboard.bestJob?.best_score),
      change: dashboard.bestJob?.best_model || t("metrics.noModel"),
      detail: dashboard.bestJob?.data?.name || t("metrics.waitingForTraining"),
      icon: TrendingUp,
      tone: "from-emerald-100 to-teal-100 text-emerald-600",
      href: dashboard.bestJob
        ? `/training-history/${dashboard.bestJob.job_id}`
        : "/training-history",
    },
    {
      label: t("metrics.awaitingDeployment"),
      value: `${dashboard.deployReadyJobs.length}`,
      change: t("metrics.completedCount", { count: dashboard.completedJobs.length }),
      detail: t("metrics.activatableModels"),
      icon: Rocket,
      tone: "from-amber-100 to-orange-100 text-amber-600",
      href: "/implement-project",
    },
  ];

  if (isLoading) {
    return <AppLoading variant="page" label={t("loading")} />;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-automl-ink dark:text-white">
            {t("title")}
          </h1>
          <p className="mt-2 text-sm font-medium text-automl-muted dark:text-white/60">
            {t("subtitle")}
          </p>
        </div>
        <span className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 shadow-sm dark:border-white/10 dark:bg-white/10 dark:text-white">
          <CalendarCheck className="h-4 w-4" />
          {t("last30Days")}
        </span>
      </section>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Link
              key={metric.label}
              href={metric.href}
              className={cn(
                "group rounded-3xl bg-gradient-to-br p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-slate-900/10",
                metric.tone,
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-black uppercase tracking-wide text-slate-500">
                    {metric.label}
                  </p>
                  <p className="mt-4 text-3xl font-black text-slate-950">
                    {metric.value}
                  </p>
                  <p className="mt-3 truncate text-sm font-black text-slate-700">
                    {metric.change}
                  </p>
                  <p className="mt-1 truncate text-xs font-semibold text-slate-500">
                    {metric.detail}
                  </p>
                </div>
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-white/85 shadow-sm transition group-hover:scale-105">
                  <Icon className="h-6 w-6" />
                </div>
              </div>
            </Link>
          );
        })}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr_0.9fr]">
        <Link
          href="/training-history"
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-automl-blue/40 hover:shadow-lg dark:border-white/10 dark:bg-white/10"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-black dark:text-white">{t("trainingOverview")}</h2>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-white/60">
              {t("currentYear")}
            </span>
          </div>
          <div className="mt-8 flex h-64 items-end gap-3 border-b border-l border-slate-100 px-2 pb-4 dark:border-white/10">
            {dashboard.monthCounts.map((count, index) => (
              <div key={monthLabels[index]} className="flex flex-1 flex-col items-center gap-3">
                <div className="flex h-48 w-full items-end rounded-full bg-slate-50 dark:bg-white/5">
                  <div
                    className="w-full rounded-full bg-gradient-to-t from-automl-blue to-cyan-300"
                    style={{
                      height: count
                        ? `${Math.max((count / dashboard.maxMonthCount) * 100, 8)}%`
                        : "4%",
                    }}
                  />
                </div>
                <span className="text-xs font-bold text-slate-400">
                  {monthLabels[index]}
                </span>
              </div>
            ))}
          </div>
        </Link>

        <Link
          href="/training-history"
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-automl-blue/40 hover:shadow-lg dark:border-white/10 dark:bg-white/10"
        >
          <h2 className="text-lg font-black dark:text-white">{t("modelGroups")}</h2>
          <div className="mt-8 flex items-center justify-center">
            <div
              className="relative h-44 w-44 rounded-full"
              style={{ background: buildConicGradient(dashboard.categories) }}
            >
              <div className="absolute inset-10 flex flex-col items-center justify-center rounded-full bg-white text-center dark:bg-automl-navy">
                <span className="text-xs font-bold text-slate-400">{t("total")}</span>
                <span className="text-2xl font-black dark:text-white">{jobs.length || allDatasets.length}</span>
              </div>
            </div>
          </div>
          <div className="mt-8 space-y-3">
            {dashboard.categories.length > 0 ? (
              dashboard.categories.map((category, index) => (
                <div key={category.label} className="flex items-center justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className="h-3 w-3 shrink-0 rounded-full"
                      style={{ backgroundColor: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }}
                    />
                    <span className="truncate text-sm font-bold text-slate-600 dark:text-white/70">
                      {category.label}
                    </span>
                  </div>
                  <span className="text-sm font-black text-slate-500 dark:text-white/60">
                    {category.percent}%
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm font-semibold text-slate-500 dark:text-white/60">
                {t("emptyGroups")}
              </p>
            )}
          </div>
        </Link>

        <Link
          href="/implement-project"
          className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-automl-blue/40 hover:shadow-lg dark:border-white/10 dark:bg-white/10"
        >
          <h2 className="text-lg font-black dark:text-white">{t("deploymentHealth")}</h2>
          <div className="mt-8 space-y-5">
            {dashboard.deployReadyJobs.slice(0, 5).length > 0 ? (
              dashboard.deployReadyJobs.slice(0, 5).map((job) => {
                const score = Math.round((job.best_score || 0) * 100);

                return (
                  <div key={job.job_id}>
                    <div className="mb-2 flex justify-between gap-3 text-sm font-bold text-slate-500 dark:text-white/60">
                      <span className="truncate">{job.data?.name || job.best_model || t("model")}</span>
                      <span>{score || 100}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100 dark:bg-white/10">
                      <div
                        className="h-2 rounded-full bg-automl-blue"
                        style={{ width: `${score || 100}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-500 dark:bg-white/5 dark:text-white/60">
                {t("emptyDeployments")}
              </div>
            )}
          </div>
        </Link>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
        <article className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="flex items-center justify-between border-b border-slate-100 p-6 dark:border-white/10">
            <h2 className="text-lg font-black dark:text-white">{t("recentTrainingRuns")}</h2>
            <Link
              href="/training-history"
              className="inline-flex items-center gap-2 text-xs font-black text-automl-blue"
            >
              {t("viewAll")} <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-black uppercase text-slate-400 dark:bg-white/5">
                <tr>
                  <th className="px-6 py-4">{t("table.runId")}</th>
                  <th className="px-6 py-4">{t("table.dataset")}</th>
                  <th className="px-6 py-4">{t("table.model")}</th>
                  <th className="px-6 py-4">{t("table.date")}</th>
                  <th className="px-6 py-4">{t("table.status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/10">
                {dashboard.recentJobs.length > 0 ? (
                  dashboard.recentJobs.map((job) => {
                    const done = isCompleted(job.status);
                    const href = done
                      ? `/training-history/${job.job_id}`
                      : "/training-history";

                    return (
                      <tr key={job.job_id} className="text-slate-600 dark:text-white/70">
                        <td className="px-6 py-4 font-black text-slate-700 dark:text-white">
                          <Link href={href} className="hover:text-automl-blue">
                            {job.job_id}
                          </Link>
                        </td>
                        <td className="px-6 py-4 font-bold">{job.data?.name || common("unknown")}</td>
                        <td className="px-6 py-4">{done ? job.best_model || common("unknown") : t("processing")}</td>
                        <td className="px-6 py-4">{formatDate(job.create_at, dateLocale, common("noData"))}</td>
                        <td className="px-6 py-4">
                          <span
                            className={cn(
                              "rounded-full px-3 py-1 text-xs font-black",
                              done
                                ? "bg-emerald-50 text-emerald-600"
                                : isRunning(job.status)
                                  ? "bg-amber-50 text-amber-700"
                                  : "bg-red-50 text-red-600",
                            )}
                          >
                            {done
                              ? t("status.completed")
                              : isRunning(job.status)
                                ? t("status.running")
                                : t("status.failed")}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center font-semibold text-slate-500">
                      {t("emptyTrainingRuns")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-black dark:text-white">{t("recentActivity")}</h2>
            <Link href={datasetHref} className="text-xs font-black text-automl-blue">
              {t("data")}
            </Link>
          </div>
          <div className="mt-6 space-y-5">
            {dashboard.activities.length > 0 ? (
              dashboard.activities.map((activity) => {
                const ActivityIcon = activity.icon;

                return (
                  <Link key={activity.id} href={activity.href} className="flex gap-4 rounded-2xl transition hover:bg-slate-50 dark:hover:bg-white/5">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
                      <ActivityIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-slate-700 dark:text-white">{activity.title}</p>
                      <p className="mt-1 truncate text-sm text-slate-500 dark:text-white/55">{activity.body}</p>
                    </div>
                    <span className="whitespace-nowrap text-xs font-bold text-slate-400">
                      {getRelativeTime(activity.timestamp)}
                    </span>
                  </Link>
                );
              })
            ) : (
              <div className="rounded-2xl bg-slate-50 p-4 text-sm font-semibold text-slate-500 dark:bg-white/5 dark:text-white/60">
                {t("emptyActivity")}
              </div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
