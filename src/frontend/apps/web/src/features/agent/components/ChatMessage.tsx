"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Bot, Check, CheckCircle2, Copy, History, RotateCcw } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { AgentError, ChatItem } from "../hooks/useAgentSession";
import { formatSize } from "../lib/agentApi";
import type { JobView, TurnTrace } from "../lib/eventAdapter";
import { formatTime } from "../lib/format";
import { card } from "../lib/ui";
import AgentActivityTimeline from "./AgentActivityTimeline";
import AgentMarkdown from "./AgentMarkdown";
import ConfigSummaryCard from "./ConfigSummaryCard";
import TrainingJobCard from "./TrainingJobCard";

export interface JobActions {
  busy: boolean;
  onSend: (text: string) => void;
  onRefreshed: (jobId: string, raw: Record<string, any>) => void;
  onActivated: (jobId: string) => void;
  onOpenDetails: () => void;
}

export function AgentAvatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-agent-primary-soft text-agent-primary-strong" aria-hidden>
      <Bot className="h-4 w-4" />
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const t = useTranslations("Agent.thread");
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          // Trình duyệt chặn clipboard.
        }
      }}
      className="agent-focus inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-automl-surface-muted"
    >
      {copied ? <Check className="h-3 w-3" aria-hidden /> : <Copy className="h-3 w-3" aria-hidden />}
      {copied ? t("copied") : t("copy")}
    </button>
  );
}

/** Thẻ cấu hình + job mà lượt chat này tạo ra - lấy từ sự kiện, không từ chữ. */
export function TraceArtifacts({ trace, jobs, actions }: { trace: TurnTrace; jobs: Record<string, JobView>; actions: JobActions }) {
  if (!trace.configs.length && !trace.jobIds.length) return null;
  return (
    <div className="space-y-2.5">
      {trace.configs.map((view, i) => (
        <ConfigSummaryCard key={i} view={view} />
      ))}
      {trace.jobIds.map((jobId) =>
        jobs[jobId] ? (
          <TrainingJobCard
            key={jobId}
            job={jobs[jobId]}
            variant="compact"
            onRefreshed={actions.onRefreshed}
            onOpenDetails={actions.onOpenDetails}
          />
        ) : null,
      )}
    </div>
  );
}

function useErrorText() {
  const t = useTranslations("Agent.errors");
  return (error: AgentError) =>
    error.code === "server" ? (error.detail ? t("server", { detail: error.detail }) : t("serverNoDetail")) : t(error.code);
}

export default function ChatMessage({ item, jobs, actions }: { item: ChatItem; jobs: Record<string, JobView>; actions: JobActions }) {
  const t = useTranslations("Agent.thread");
  const tUpload = useTranslations("Agent.upload");
  const tTypes = useTranslations("Agent.problemTypes");
  const locale = useLocale();
  const errorText = useErrorText();
  const { busy, onSend } = actions;

  switch (item.kind) {
    case "user":
      return (
        <div className="flex flex-col items-end gap-1">
          <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-agent-primary px-4 py-2.5 text-[14.5px] text-agent-primary-fg shadow-sm">
            <span className="sr-only">{t("you")}: </span>
            {item.text}
          </div>
          <span className="text-[11px] text-automl-muted">{formatTime(item.at, locale)}</span>
        </div>
      );

    case "agent":
      return (
        <article className="flex gap-3">
          <AgentAvatar />
          <div className="min-w-0 flex-1 space-y-2.5">
            <p className="text-xs font-semibold text-automl-muted-strong">{t("agentName")}</p>
            <AgentActivityTimeline trace={item.trace} />
            <AgentMarkdown text={item.text} />
            <TraceArtifacts trace={item.trace} jobs={jobs} actions={actions} />
            <div className="flex items-center gap-2 text-[11px] text-automl-muted">
              <span>{formatTime(item.at, locale)}</span>
              <CopyButton text={item.text} />
            </div>
          </div>
        </article>
      );

    case "upload":
      return (
        <div className="rounded-2xl border border-agent-success/30 bg-agent-success-soft p-3.5 text-agent-success">
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
            <div className="min-w-0 text-sm">
              <p className="font-semibold">{tUpload.rich("added", { name: item.dataset.name, b: (chunks) => <strong>{chunks}</strong> })}</p>
              <p className="mt-0.5 truncate text-xs opacity-80">
                {item.dataset.filename} · {formatSize(item.dataset.size_bytes)} · {tTypes(item.dataset.type === "regression" ? "regression" : "classification")}
              </p>
            </div>
          </div>
          <div className="mt-2.5 flex flex-wrap gap-2 pl-7">
            {(["analyze", "train"] as const).map((action) => (
              <button
                key={action}
                type="button"
                onClick={() => onSend(tUpload(`${action}Prompt`, { name: item.dataset.name }))}
                disabled={busy}
                className="agent-focus rounded-full bg-automl-surface px-3 py-1 text-xs font-semibold text-agent-success ring-1 ring-agent-success/30 transition-colors hover:bg-automl-surface-muted disabled:opacity-50"
              >
                {tUpload(action)}
              </button>
            ))}
          </div>
        </div>
      );

    case "error":
      return (
        <div className="space-y-2.5">
          {item.trace && <AgentActivityTimeline trace={item.trace} />}
          <div role="alert" className="flex items-start gap-2.5 rounded-2xl border border-agent-error/30 bg-agent-error-soft p-3.5 text-sm text-agent-error">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="break-words">{errorText(item.error)}</p>
              {item.retryText && (
                <button
                  type="button"
                  onClick={() => onSend(item.retryText!)}
                  disabled={busy}
                  className="agent-focus mt-2 inline-flex items-center gap-1 rounded-full bg-automl-surface px-3 py-1 text-xs font-semibold text-agent-error ring-1 ring-agent-error/30 hover:bg-automl-surface-muted disabled:opacity-50"
                >
                  <RotateCcw className="h-3 w-3" aria-hidden /> {t("retry")}
                </button>
              )}
            </div>
          </div>
        </div>
      );

    case "job": {
      const job = jobs[item.jobId];
      return job ? (
        <TrainingJobCard
          job={job}
          busy={busy}
          onAsk={onSend}
          onRefreshed={actions.onRefreshed}
          onActivated={actions.onActivated}
        />
      ) : null;
    }

    case "restored":
      return (
        <div className={cn(card, "space-y-2.5 bg-agent-info-soft p-3.5")}>
          <p className="flex items-start gap-2 text-sm text-agent-info">
            <History className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {t("restored")}
          </p>
          {item.jobIds.length > 0 && (
            <>
              <p className="text-xs font-semibold text-automl-muted-strong">{t("restoredJobs")}</p>
              {item.jobIds.map((jobId) =>
                jobs[jobId] ? (
                  <TrainingJobCard
                    key={jobId}
                    job={jobs[jobId]}
                    busy={busy}
                    onAsk={onSend}
                    onRefreshed={actions.onRefreshed}
                    onActivated={actions.onActivated}
                  />
                ) : null,
              )}
            </>
          )}
        </div>
      );
  }
}
