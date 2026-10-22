"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Check, ChevronDown, Copy, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { groupConfigErrors, type ConfigField, type ConfigView } from "../lib/eventAdapter";
import { formatDuration, shortId } from "../lib/format";
import { card, ghostButton } from "../lib/ui";

export function ValidationBadge({ valid }: { valid: boolean | null }) {
  const t = useTranslations("Agent.config");
  const [Icon, text, tone] =
    valid === true
      ? [ShieldCheck, t("verified"), "bg-agent-success-soft text-agent-success"]
      : valid === false
        ? [ShieldAlert, t("invalid"), "bg-agent-error-soft text-agent-error"]
        : [ShieldQuestion, t("unchecked"), "bg-automl-surface-muted text-automl-muted-strong"];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", tone)}>
      <Icon className="h-3.5 w-3.5" aria-hidden /> {text}
    </span>
  );
}

function Field({ label, value, errors }: { label: string; value: ReactNode; errors?: string[] }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-automl-muted">{label}</dt>
      <dd className={cn("mt-0.5 truncate text-[13px] font-semibold", errors?.length ? "text-agent-error" : "text-automl-ink")}>{value}</dd>
      {errors?.map((error, i) => (
        <dd key={i} className="mt-0.5 break-words text-[11px] text-agent-error">{error}</dd>
      ))}
    </div>
  );
}

/**
 * Cấu hình AutoML. Chỉ đọc: agent gửi job ngay sau khi kiểm định qua, không
 * có API sửa rồi chạy lại.
 */
export default function ConfigSummaryCard({ view }: { view: ConfigView }) {
  const t = useTranslations("Agent.config");
  const tTypes = useTranslations("Agent.problemTypes");
  const tDuration = useTranslations("Agent.duration");
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const config = view.config;
  const groups = groupConfigErrors(view.errors);
  const byField = new Map<ConfigField, string[]>(groups);

  const copy = async () => {
    if (!config) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(config, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Trình duyệt chặn clipboard: không có gì để làm.
    }
  };

  const problemType = config?.problem_type as string | undefined;

  return (
    <section className={cn(card, "p-3.5")}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] font-bold text-automl-ink">
          {t("title")}
          {view.configId && <span className="ml-1.5 font-mono text-[11px] font-normal text-automl-muted">{view.configId}</span>}
        </p>
        <ValidationBadge valid={view.valid} />
      </header>

      {/* Config không hợp lệ thì backend không trả config - chỉ có lỗi, nhóm theo trường. */}
      {!config && groups.length > 0 && (
        <div className="mt-2.5 rounded-xl bg-agent-error-soft px-3 py-2 text-xs text-agent-error">
          <p className="font-semibold">{t("errorsTitle")}</p>
          <dl className="mt-1 space-y-1">
            {groups.map(([field, errors]) => (
              <div key={field}>
                <dt className="font-semibold">{t(`fields.${field}`)}</dt>
                {errors.map((error, i) => (
                  <dd key={i} className="break-words">{error}</dd>
                ))}
              </div>
            ))}
          </dl>
        </div>
      )}

      {config && (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
            <Field
              label={t("problemType")}
              value={problemType === "classification" || problemType === "regression" ? tTypes(problemType) : problemType ?? "—"}
              errors={byField.get("problem_type")}
            />
            <Field label={t("target")} value={config.target ?? "—"} errors={byField.get("target")} />
            <Field label={t("metric")} value={config.metric_sort ?? "—"} errors={byField.get("metric")} />
            <Field
              label={t("featureCount")}
              value={Array.isArray(config.list_feature) ? config.list_feature.length : "—"}
              errors={byField.get("features")}
            />
            <Field label={t("algorithm")} value={config.search_algorithm ?? "—"} errors={byField.get("algorithm")} />
            <Field
              label={t("maxTime")}
              value={typeof config.max_time === "number" ? formatDuration(config.max_time, tDuration) : t("defaultTime")}
              errors={byField.get("max_time")}
            />
          </dl>
          {view.datasetId && <p className="mt-2 font-mono text-[11px] text-automl-muted">dataset #{shortId(view.datasetId, 10)}</p>}

          <div className="mt-2.5 flex items-center gap-1">
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className={ghostButton}>
              {t("details")}
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", open && "rotate-180")} aria-hidden />
            </button>
            <button type="button" onClick={copy} className={ghostButton}>
              {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
              {copied ? t("copied") : t("copy")}
            </button>
          </div>
          {open && (
            // JSON.stringify + text node: React tự escape, không render HTML.
            <pre className="mt-2 max-h-64 overflow-auto rounded-xl bg-slate-950 p-3 font-mono text-[11.5px] leading-relaxed text-slate-100">
              {JSON.stringify(config, null, 2)}
            </pre>
          )}
        </>
      )}
    </section>
  );
}
