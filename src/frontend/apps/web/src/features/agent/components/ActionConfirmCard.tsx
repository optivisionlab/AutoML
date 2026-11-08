"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle2, Hand, Loader2, Power, PowerOff, Rocket, XCircle } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { ActionOutcome } from "../hooks/useAgentSession";
import { isProblemType } from "../hooks/useAgentSession";
import type { PendingActionView } from "../lib/actions";
import { formatDuration, formatScore, shortId } from "../lib/format";
import { card, pillButton, primaryPill } from "../lib/ui";

interface Props {
  action: PendingActionView;
  /** Agent đang trả lời: server từ chối xác nhận (409) - khoá nút cho tới khi xong. */
  locked: boolean;
  onDecide: (actionId: string, decision: "confirm" | "reject", autoActivate?: boolean) => Promise<ActionOutcome>;
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-automl-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-[13px] font-semibold text-automl-ink">{value}</dd>
    </div>
  );
}

function constraintsText(list: { metric: string; op: string; value: number }[] | undefined): string {
  return (list ?? []).map((c) => `${c.metric} ${c.op} ${c.value}`).join(", ");
}

/**
 * Thẻ xác nhận hành động thật (audit AG-01). Nội dung lấy từ `summary` do server dựng từ dữ liệu thật
 * (config đã kiểm, bản ghi job) - không phải chữ LLM viết - nên người dùng thấy đúng việc sẽ xảy ra.
 * Agent không tự làm được việc này: chỉ cú bấm ở đây (POST /agent/confirm kèm mã một lần) mới chạy.
 */
export default function ActionConfirmCard({ action, locked, onDecide }: Props) {
  const t = useTranslations("Agent.action");
  const tTypes = useTranslations("Agent.problemTypes");
  const tDuration = useTranslations("Agent.duration");
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const s = action.summary;
  const pending = action.status === "pending";
  const submitting = action.status === "submitting";

  const decide = async (decision: "confirm" | "reject", autoActivate?: boolean) => {
    setOutcome(null);
    const result = await onDecide(action.actionId, decision, autoActivate);
    setOutcome(result === "ok" ? null : result);
  };

  const Icon = action.kind === "train" ? Rocket : action.kind === "deactivate" ? PowerOff : Power;
  const title =
    action.kind === "train"
      ? t("title.train")
      : action.kind === "activate"
        ? t("title.activate")
        : action.kind === "deactivate"
          ? t("title.deactivate")
          : t("title.autoActivate");

  return (
    <section
      className={cn(card, "border-agent-primary/40 p-3.5", !pending && !submitting && "opacity-80")}
      aria-label={title}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[13px] font-bold text-automl-ink">
          <Icon className="h-4 w-4 text-agent-primary-strong" aria-hidden />
          {title}
        </p>
        <StatusBadge action={action} />
      </header>

      {action.kind === "train" && (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
          <Field label={t("dataset")} value={s.dataset_name || (s.dataset_id ? `#${shortId(s.dataset_id, 10)}` : "—")} />
          <Field label={t("target")} value={s.target ?? "—"} />
          <Field label={t("problemType")} value={isProblemType(s.problem_type) ? tTypes(s.problem_type) : s.problem_type ?? "—"} />
          <Field label={t("metric")} value={s.metric_sort ?? "—"} />
          <Field label={t("features")} value={typeof s.feature_count === "number" ? s.feature_count : "—"} />
          <Field label={t("maxTime")} value={typeof s.max_time === "number" ? formatDuration(s.max_time, tDuration) : "—"} />
        </dl>
      )}
      {action.kind === "train" && !!s.features?.length && (
        <p className="mt-2 break-words text-[11.5px] text-automl-muted-strong">
          {t("featureList", { list: s.features.join(", "), more: Math.max(0, (s.feature_count ?? 0) - s.features.length) })}
        </p>
      )}

      {(action.kind === "activate" || action.kind === "deactivate") && (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
          <Field label={t("job")} value={s.job_id ? shortId(s.job_id, 10) : "—"} />
          <Field label={t("dataset")} value={s.dataset_name || "—"} />
          <Field label={t("bestModel")} value={s.best_model ?? "—"} />
          <Field label={s.metric_sort ?? t("score")} value={formatScore(s.best_score ?? null)} />
        </dl>
      )}

      {action.kind === "auto_activate" && (
        <p className="mt-2.5 text-[13px] text-automl-ink">
          {s.unconditional || !s.constraints?.length
            ? t("autoUnconditional", { job: shortId(String(s.job_id ?? ""), 10) })
            : t("autoConditional", { job: shortId(String(s.job_id ?? ""), 10), constraints: constraintsText(s.constraints) })}
        </p>
      )}

      {!!s.duplicate_of?.length && (
        <p className="mt-2.5 flex items-start gap-1.5 rounded-xl bg-agent-warning-soft px-3 py-2 text-xs text-agent-warning">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
          {t("duplicate", { jobs: s.duplicate_of.map((id) => shortId(id, 10)).join(", ") })}
        </p>
      )}
      {s.score_source && s.score_source !== "holdout" && (action.kind === "activate" || action.kind === "auto_activate") && (
        <p className="mt-2.5 flex items-start gap-1.5 rounded-xl bg-agent-warning-soft px-3 py-2 text-xs text-agent-warning">
          <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
          {s.score_source === "cv" ? t("cvScore") : t("unknownScore")}
        </p>
      )}

      {action.error && (action.status === "failed" || action.status === "expired" || pending) && (
        <p className="mt-2.5 break-words text-xs text-agent-error">{action.error}</p>
      )}
      {outcome && <p className="mt-2 text-xs text-agent-error">{t(`errors.${outcome}`)}</p>}

      {(pending || submitting) && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {action.kind === "train" && action.offersAutoActivate ? (
            <>
              <button type="button" className={primaryPill} disabled={!pending || locked} onClick={() => decide("confirm", false)}>
                {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
                {t("confirmTrain")}
              </button>
              <button type="button" className={pillButton} disabled={!pending || locked} onClick={() => decide("confirm", true)}>
                {t("confirmTrainAuto", {
                  when: s.auto_activate_constraints?.length ? constraintsText(s.auto_activate_constraints) : t("always"),
                })}
              </button>
            </>
          ) : (
            <button type="button" className={primaryPill} disabled={!pending || locked} onClick={() => decide("confirm")}>
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
              {t(`confirm.${action.kind}`)}
            </button>
          )}
          <button type="button" className={pillButton} disabled={!pending || locked} onClick={() => decide("reject")}>
            {t("reject")}
          </button>
          {locked && <span className="text-[11px] text-automl-muted">{t("waitForReply")}</span>}
        </div>
      )}
    </section>
  );
}

function StatusBadge({ action }: { action: PendingActionView }) {
  const t = useTranslations("Agent.action.status");
  const [Icon, tone] =
    action.status === "done"
      ? [CheckCircle2, "bg-agent-success-soft text-agent-success"]
      : action.status === "failed"
        ? [XCircle, "bg-agent-error-soft text-agent-error"]
        : action.status === "pending" || action.status === "submitting"
          ? [Hand, "bg-agent-primary-soft text-agent-primary-strong"]
          : [XCircle, "bg-automl-surface-muted text-automl-muted-strong"];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", tone)}>
      <Icon className="h-3.5 w-3.5" aria-hidden /> {t(action.status)}
    </span>
  );
}
