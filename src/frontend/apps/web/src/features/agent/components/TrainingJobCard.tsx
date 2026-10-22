"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Copy,
  ExternalLink,
  HelpCircle,
  Loader2,
  PanelRight,
  Power,
  RefreshCw,
  Send,
  Trophy,
  XCircle,
} from "lucide-react";
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
import { useLazyGetJobsQuery } from "@/core/api/jobApi";
import { useActivateModelMutation } from "@/core/api/inferenceApi";
import { cn } from "@/shared/lib/utils";
import { isJobActive, metricDirection, type JobStatus, type JobView, type LeaderboardRow } from "../lib/eventAdapter";
import { formatDuration, formatScore, formatTime, shortId } from "../lib/format";
import { card, pillButton, primaryPill } from "../lib/ui";
import InferenceForm from "./InferenceForm";
import { useApiErrorText } from "./useApiErrorText";

const STATUS: Record<JobStatus, { icon: typeof Loader2; tone: string }> = {
  submitted: { icon: Send, tone: "bg-agent-info-soft text-agent-info" },
  running: { icon: Loader2, tone: "bg-agent-primary-soft text-agent-primary-strong" },
  completed: { icon: CheckCircle2, tone: "bg-agent-success-soft text-agent-success" },
  failed: { icon: XCircle, tone: "bg-agent-error-soft text-agent-error" },
  cancelled: { icon: Ban, tone: "bg-automl-surface-muted text-automl-muted-strong" },
  unknown: { icon: HelpCircle, tone: "bg-agent-warning-soft text-agent-warning" },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const t = useTranslations("Agent.job.status");
  const { icon: Icon, tone } = STATUS[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", tone)}>
      <Icon className={cn("h-3.5 w-3.5", status === "running" && "animate-spin motion-reduce:animate-none")} aria-hidden />
      {t(status)}
    </span>
  );
}

/** Đồng hồ cho "đã chạy bao lâu" - tính từ lúc gửi job, không phải % tiến độ. */
function useNow(active: boolean, interval = 15_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), interval);
    return () => window.clearInterval(timer);
  }, [active, interval]);
  return now;
}

function CopyId({ id }: { id: string }) {
  const t = useTranslations("Agent.job");
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(id);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          // Trình duyệt chặn clipboard.
        }
      }}
      aria-label={t("copyId", { id })}
      title={id}
      className="agent-focus inline-flex items-center gap-1 rounded-md px-1 font-mono text-[11px] text-automl-muted hover:bg-automl-surface-muted"
    >
      #{shortId(id)}
      {copied ? <Check className="h-3 w-3" aria-hidden /> : <Copy className="h-3 w-3" aria-hidden />}
    </button>
  );
}

type SortKey = "rank" | "model" | "score";

function Leaderboard({ job }: { job: JobView }) {
  const t = useTranslations("Agent.job");
  const [sort, setSort] = useState<{ key: SortKey; asc: boolean }>({ key: "rank", asc: true });
  // Hạng giữ nguyên thứ tự backend xếp; sắp xếp chỉ đổi cách xem.
  const rows = useMemo(() => {
    const ranked = (job.leaderboard ?? []).map((row, i) => ({ ...row, rank: i + 1 }));
    const dir = sort.asc ? 1 : -1;
    return [...ranked].sort((a, b) => {
      if (sort.key === "model") return a.model.localeCompare(b.model) * dir;
      if (sort.key === "score") return ((a.score ?? -Infinity) - (b.score ?? -Infinity)) * dir;
      return (a.rank - b.rank) * dir;
    });
  }, [job.leaderboard, sort]);

  if (!rows.length) return null;
  const direction = metricDirection(job.metric);

  const header = (key: SortKey, label: string, align = "text-left") => {
    const activeSort = sort.key === key;
    const Icon = !activeSort ? ArrowUpDown : sort.asc ? ArrowUp : ArrowDown;
    return (
      <th scope="col" aria-sort={activeSort ? (sort.asc ? "ascending" : "descending") : "none"} className={cn("px-3 py-1.5 font-semibold", align)}>
        <button
          type="button"
          onClick={() => setSort((prev) => ({ key, asc: prev.key === key ? !prev.asc : true }))}
          aria-label={t("sortBy", { column: label })}
          className="agent-focus inline-flex items-center gap-1 rounded"
        >
          {label}
          <Icon className="h-3 w-3 opacity-60" aria-hidden />
        </button>
      </th>
    );
  };

  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-automl-line">
      <table className="w-full text-[12.5px]">
        <caption className="sr-only">{t("leaderboardCaption", { metric: job.metric ?? "" })}</caption>
        <thead className="bg-automl-surface-muted text-automl-muted-strong">
          <tr>
            {header("rank", t("rank"))}
            {header("model", t("model"))}
            {header("score", job.metric ?? "score", "text-right")}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: LeaderboardRow & { rank: number }) => (
            <tr key={`${row.model}-${row.rank}`} className="border-t border-automl-line">
              <td className="px-3 py-1.5 tabular-nums text-automl-muted">{row.rank}</td>
              <td className={cn("px-3 py-1.5 text-automl-ink", row.model === job.bestModel && "font-semibold")}>{row.model}</td>
              <td className="px-3 py-1.5 text-right font-mono tabular-nums text-automl-ink">{formatScore(row.score)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {direction && (
        <p className="border-t border-automl-line px-3 py-1.5 text-[11px] text-automl-muted">
          {direction === "lower" ? t("lowerBetter") : t("higherBetter")}
        </p>
      )}
    </div>
  );
}

function Results({ job }: { job: JobView }) {
  const t = useTranslations("Agent.job");
  const direction = metricDirection(job.metric);
  const DirectionIcon = direction === "lower" ? ArrowDown : ArrowUp;
  const verification = job.verification;
  const otherScores = Object.entries(job.bestScores ?? {}).filter(([k]) => k.toLowerCase() !== job.metric?.toLowerCase());

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-agent-success-soft px-3 py-2.5 text-agent-success">
        <Trophy className="h-5 w-5 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wide opacity-80">{t("best")}</p>
          <p className="truncate text-sm font-bold">{job.bestModel ?? "—"}</p>
        </div>
        <div className="text-right">
          <p className="flex items-center justify-end gap-1 text-[11px] font-medium uppercase tracking-wide opacity-80">
            {job.metric}
            {direction && <DirectionIcon className="h-3 w-3" aria-label={direction === "lower" ? t("lowerBetter") : t("higherBetter")} />}
          </p>
          <p className="font-mono text-base font-bold tabular-nums">{formatScore(job.bestScore)}</p>
        </div>
      </div>

      {otherScores.length > 0 && (
        <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {otherScores.map(([metric, score]) => (
            <div key={metric} className="flex gap-1">
              <dt className="text-automl-muted">{metric}</dt>
              <dd className="font-mono tabular-nums text-automl-ink">{formatScore(score)}</dd>
            </div>
          ))}
        </dl>
      )}

      {verification && verification.passed !== null && (
        <div
          className={cn(
            "mt-2 rounded-xl px-3 py-2 text-xs",
            verification.passed ? "bg-agent-success-soft text-agent-success" : "bg-agent-warning-soft text-agent-warning",
          )}
        >
          <p className="font-semibold">{verification.passed ? t("passed") : t("notPassed")}</p>
          <ul className="mt-0.5">
            {verification.checks.map((c, i) => (
              <li key={i}>
                {t("checkLine", {
                  metric: c.metric,
                  op: c.op,
                  value: String(c.value),
                  score: c.score === null ? t("noScore") : formatScore(c.score),
                })}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Leaderboard job={job} />
      {typeof job.modelsScored === "number" && <p className="mt-1.5 text-[11px] text-automl-muted">{t("modelsScored", { count: job.modelsScored })}</p>}
    </div>
  );
}

interface Props {
  job: JobView;
  /** compact: dòng trạng thái gọn trong lượt chat đã gửi job. full: thẻ kết quả + thao tác. */
  variant?: "compact" | "full";
  busy?: boolean;
  onAsk?: (text: string) => void;
  onRefreshed?: (jobId: string, raw: Record<string, any>) => void;
  onActivated?: (jobId: string) => void;
  onOpenDetails?: () => void;
}

// Job của phiên này luôn mới - vài trang đầu (mới nhất trước) là đủ.
const REFRESH_MAX_PAGES = 3;

export default function TrainingJobCard({ job, variant = "full", busy = false, onAsk, onRefreshed, onActivated, onOpenDetails }: Props) {
  const t = useTranslations("Agent.job");
  const tDuration = useTranslations("Agent.duration");
  const locale = useLocale();
  const errorText = useApiErrorText();
  const [fetchJobs, jobsQuery] = useLazyGetJobsQuery();
  const [activateModel, activation] = useActivateModelMutation();
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [showPredict, setShowPredict] = useState(false);

  const active = isJobActive(job);
  const now = useNow(active);
  const runningFor = job.submittedAt ? (now - job.submittedAt) / 1000 : null;
  const full = variant === "full";

  const refresh = async () => {
    setRefreshError(null);
    try {
      for (let page = 1; page <= REFRESH_MAX_PAGES; page++) {
        const res = await fetchJobs({ current_page: page, page_size: 100, sort_time: "desc" }).unwrap();
        const list = ((res as unknown as { data?: Record<string, any>[] })?.data ?? []) as Record<string, any>[];
        const found = list.find((item) => item._id === job.jobId || item.id === job.jobId);
        if (found) {
          onRefreshed?.(job.jobId, found);
          return;
        }
        if (list.length < 100) break;
      }
      setRefreshError(t("notFound"));
    } catch (error) {
      setRefreshError(t("refreshFailed", { detail: errorText(error) }));
    }
  };

  const activate = async () => {
    setActivationError(null);
    try {
      await activateModel({ jobId: job.jobId, activate: 1 }).unwrap();
      onActivated?.(job.jobId);
      setShowPredict(true);
    } catch (error) {
      setActivationError(errorText(error));
    }
  };

  return (
    <section
      className={cn(card, "p-3.5", job.status === "failed" && "border-agent-error/40")}
      aria-label={t("label", { id: shortId(job.jobId) })}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[13px] font-bold text-automl-ink">
          {t("title")} <CopyId id={job.jobId} />
        </p>
        <div className="flex items-center gap-1.5">
          <JobStatusBadge status={job.status} />
          <button
            type="button"
            onClick={refresh}
            disabled={jobsQuery.isFetching}
            aria-label={jobsQuery.isFetching ? t("refreshing") : t("refresh")}
            title={t("refresh")}
            className="agent-focus rounded-md p-1 text-automl-muted transition-colors hover:bg-automl-surface-muted hover:text-automl-ink disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", jobsQuery.isFetching && "animate-spin motion-reduce:animate-none")} aria-hidden />
          </button>
        </div>
      </header>

      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-automl-muted-strong">
        {job.dataset && (
          <div className="flex gap-1">
            <dt className="text-automl-muted">{t("dataset")}</dt>
            <dd className="font-medium">{job.dataset}</dd>
          </div>
        )}
        {job.metric && (
          <div className="flex gap-1">
            <dt className="text-automl-muted">{t("metric")}</dt>
            <dd className="font-medium">{job.metric}</dd>
          </div>
        )}
        {job.configId && full && (
          <div className="flex gap-1">
            <dt className="text-automl-muted">{t("configId")}</dt>
            <dd className="font-mono">{job.configId}</dd>
          </div>
        )}
        {job.submittedAt && (
          <div className="flex gap-1">
            <dt className="text-automl-muted">{t("submittedAt")}</dt>
            <dd>{formatTime(job.submittedAt, locale)}</dd>
          </div>
        )}
        {job.finishedAt && (
          <div className="flex gap-1">
            <dt className="text-automl-muted">{t("finishedAt")}</dt>
            <dd>{formatTime(job.finishedAt, locale)}</dd>
          </div>
        )}
        {active && runningFor !== null && (
          <div className="flex items-center gap-1">
            <Clock3 className="h-3 w-3" aria-hidden />
            <dt className="sr-only">{t("status.running")}</dt>
            <dd>{t("runningFor", { duration: formatDuration(runningFor, tDuration) })}</dd>
          </div>
        )}
        <div className="flex gap-1">
          <dt className="text-automl-muted">{t("updatedAt")}</dt>
          <dd>
            {formatTime(job.lastUpdated, locale)}
            {job.source && <span className="text-automl-muted"> ({job.source === "api" ? t("sourceApi") : t("sourceStream")})</span>}
          </dd>
        </div>
      </dl>

      {active && (
        <div className="mt-2.5">
          {/* Backend không báo % tiến độ - thanh chạy vô định, không phải ước lượng. */}
          <div className="h-1 overflow-hidden rounded-full bg-agent-primary-soft" role="progressbar" aria-label={t("indeterminate")}>
            <div className="h-full w-1/3 animate-[agent-indeterminate_1.6s_ease-in-out_infinite] rounded-full bg-agent-primary motion-reduce:animate-none" />
          </div>
          {full && <p className="mt-1.5 text-[11px] text-automl-muted">{t("background")}</p>}
        </div>
      )}

      {job.warning && (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-agent-warning-soft px-2.5 py-1.5 text-xs text-agent-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden /> {job.warning}
        </p>
      )}

      {(job.status === "failed" || job.status === "cancelled" || job.status === "unknown") && (
        <p className="mt-2 break-words rounded-lg bg-agent-error-soft px-2.5 py-1.5 text-xs text-agent-error">{job.error ?? t("noReason")}</p>
      )}

      {refreshError && <p role="alert" className="mt-2 text-xs text-agent-error">{refreshError}</p>}

      {full && job.status === "completed" && <Results job={job} />}

      <div className="mt-3 flex flex-wrap gap-2">
        {!full && onOpenDetails && (
          <button type="button" onClick={onOpenDetails} className={pillButton}>
            <PanelRight className="h-3.5 w-3.5" aria-hidden /> {t("details")}
          </button>
        )}
        {full && job.status === "completed" && (
          <>
            {job.activated ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-agent-success-soft px-3 py-1.5 text-xs font-semibold text-agent-success">
                <Power className="h-3.5 w-3.5" aria-hidden /> {t("activated")}
              </span>
            ) : (
              <button type="button" onClick={() => setConfirmActivate(true)} disabled={activation.isLoading} className={primaryPill}>
                {activation.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> : <Power className="h-3.5 w-3.5" aria-hidden />}
                {activation.isLoading ? t("activating") : t("activate")}
              </button>
            )}
            <button type="button" onClick={() => setShowPredict((v) => !v)} aria-expanded={showPredict} className={pillButton}>
              {/* Nhãn lấy từ namespace predict để khớp tiêu đề form. */}
              <PredictLabel />
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", showPredict && "rotate-180")} aria-hidden />
            </button>
          </>
        )}
        {full && !active && onAsk && (
          <button
            type="button"
            onClick={() => onAsk(job.status === "completed" ? t("explainPrompt", { id: job.jobId }) : t("whyFailedPrompt", { id: job.jobId }))}
            disabled={busy}
            className={pillButton}
          >
            {job.status === "completed" ? t("explain") : t("whyFailed")}
          </button>
        )}
        {full && job.status === "completed" && (
          <Link href={`/implement-project/${job.jobId}`} className={pillButton}>
            {t("deployPage")} <ExternalLink className="h-3 w-3" aria-hidden />
          </Link>
        )}
      </div>

      {activationError && <p role="alert" className="mt-2 text-xs text-agent-error">{activationError}</p>}

      {full && job.status === "completed" && showPredict && (
        <div className="mt-3 rounded-xl border border-automl-line p-3">
          <InferenceForm jobId={job.jobId} activated={!!job.activated} />
        </div>
      )}

      <AlertDialog open={confirmActivate} onOpenChange={setConfirmActivate}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("activateConfirmTitle", { id: shortId(job.jobId) })}</AlertDialogTitle>
            <AlertDialogDescription>{t("activateConfirmDesc")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={activate}>{t("confirm")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function PredictLabel() {
  const t = useTranslations("Agent.predict");
  return <>{t("title")}</>;
}

