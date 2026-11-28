"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, CheckCircle2, ChevronDown, CircleHelp, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { currentActivity, type ActivityStep, type StepStatus, type TurnTrace } from "../lib/eventAdapter";
import { formatDuration } from "../lib/format";
import { useAgentLabels } from "./labels";

const STATUS_TONE: Record<StepStatus, string> = {
  running: "text-agent-primary-strong",
  success: "text-agent-success",
  failed: "text-agent-error",
  needs_input: "text-agent-warning",
};

function StatusIcon({ status, validation }: { status: StepStatus; validation?: boolean }) {
  // Biểu tượng luôn đi kèm chữ trạng thái - không mã hoá trạng thái chỉ bằng màu.
  const cls = cn("h-4 w-4", STATUS_TONE[status]);
  if (status === "running") return <Loader2 className={cn(cls, "animate-spin motion-reduce:animate-none")} aria-hidden />;
  if (status === "failed") return <XCircle className={cls} aria-hidden />;
  if (status === "needs_input") return <CircleHelp className={cls} aria-hidden />;
  if (validation) return <ShieldCheck className={cls} aria-hidden />;
  return <CheckCircle2 className={cls} aria-hidden />;
}

function StepRow({ step, last }: { step: ActivityStep; last: boolean }) {
  const t = useTranslations("Agent.activity");
  const tDuration = useTranslations("Agent.duration");
  const { agentName, toolName } = useAgentLabels();
  const duration = step.startedAt && step.endedAt ? step.endedAt - step.startedAt : null;
  const label = step.kind === "validation" ? t("validation") : agentName(step.agent);
  const statusText =
    step.kind === "validation" ? (step.status === "success" ? t("valid") : t("invalid")) : t(`stepStatus.${step.status}`);

  return (
    <li className="relative flex gap-3 pb-3 last:pb-0">
      {!last && <span className="absolute left-[7.5px] top-5 h-[calc(100%-12px)] w-px bg-automl-line" aria-hidden />}
      <span className="relative mt-0.5 shrink-0">
        <StatusIcon status={step.status} validation={step.kind === "validation"} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-[13px]">
          <span className="font-semibold text-automl-ink">{label}</span>
          <span className={cn("text-xs", STATUS_TONE[step.status])}>
            {statusText}
            {duration !== null && duration >= 1 ? ` · ${formatDuration(duration, tDuration)}` : ""}
          </span>
        </p>
        {step.task && <p className="mt-0.5 line-clamp-2 text-xs text-automl-muted">{step.task}</p>}

        {step.tools.length > 0 && (
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {step.tools.map((tool, i) => (
              <li
                key={i}
                title={tool.error}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]",
                  tool.status === "failed" ? "bg-agent-error-soft text-agent-error" : "bg-automl-surface-muted text-automl-muted-strong",
                )}
              >
                {tool.status === "running" && <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" aria-hidden />}
                {tool.status === "failed" && <AlertCircle className="h-3 w-3" aria-hidden />}
                {toolName(tool.name)}
                {tool.status === "failed" && <span className="sr-only"> {t("toolFailed")}</span>}
              </li>
            ))}
          </ul>
        )}

        {step.missing.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 rounded-lg bg-agent-warning-soft px-2.5 py-1.5 text-xs font-medium text-agent-warning">
            {step.missing.map((question, i) => (
              <li key={i}>{question}</li>
            ))}
          </ul>
        )}
        {step.errors.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 text-xs text-agent-error">
            {step.errors.map((error, i) => (
              <li key={i} className="break-words">• {error}</li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

/** Câu ngắn "đang làm gì" lấy từ bước + tool đang chạy - dùng cả ở ô nhập. */
export function useActivityText(trace: TurnTrace | null): string | null {
  const t = useTranslations("Agent.activity");
  const { agentName, toolName } = useAgentLabels();
  if (!trace) return null;
  const now = currentActivity(trace);
  if (!now) return trace.steps.length ? t("working") : t("managerThinking");
  return now.tool ? t("nowTool", { agent: agentName(now.agent), tool: toolName(now.tool) }) : t("nowAgent", { agent: agentName(now.agent) });
}

/**
 * Các bước agent đã thực sự chạy trong một lượt. Chỉ có bước nào phát sự kiện
 * thì mới hiện - câu hỏi đơn giản không qua sub-agent thì không có timeline.
 */
export default function AgentActivityTimeline({ trace, live = false }: { trace: TurnTrace; live?: boolean }) {
  const t = useTranslations("Agent.activity");
  const tErrors = useTranslations("Agent.errors");
  const activityText = useActivityText(live ? trace : null);
  const [open, setOpen] = useState(false);
  const expanded = live || open;
  const steps = trace.steps;
  if (!steps.length && !live) return null;

  const failed = steps.some((s) => s.status === "failed");
  const needsInput = steps.some((s) => s.status === "needs_input");
  const summary = live
    ? activityText
    : [t("steps", { count: steps.length }), failed ? t("hasError") : needsInput ? t("needsInput") : null].filter(Boolean).join(" · ");

  return (
    <section className="rounded-2xl border border-automl-line bg-automl-surface-muted/50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={live}
        aria-expanded={expanded}
        className="agent-focus flex w-full items-center justify-between gap-2 rounded-2xl px-3.5 py-2.5 text-left text-xs font-semibold text-automl-muted-strong disabled:cursor-default"
      >
        <span className="flex min-w-0 items-center gap-2">
          {live && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-agent-primary motion-reduce:animate-none" aria-hidden />}
          <span className="shrink-0">{t("title")}</span>
          <span className="truncate font-normal text-automl-muted">· {summary}</span>
        </span>
        {!live && <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform duration-200", expanded && "rotate-180")} aria-hidden />}
      </button>
      {expanded && (
        <div className="border-t border-automl-line px-3.5 py-3">
          {steps.length === 0 ? (
            <p className="text-xs text-automl-muted">{t("managerThinking")}</p>
          ) : (
            <ol>
              {steps.map((step, i) => (
                <StepRow key={step.id} step={step} last={i === steps.length - 1} />
              ))}
            </ol>
          )}
          {trace.error && (
            <p className="mt-2 text-xs text-agent-error">{trace.error === "budget" ? tErrors("budget") : trace.error}</p>
          )}
        </div>
      )}
    </section>
  );
}
