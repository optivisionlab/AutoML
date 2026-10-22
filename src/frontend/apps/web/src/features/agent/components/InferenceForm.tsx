"use client";

import { FormEvent, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { useGetModelDeploymentInfoQuery, usePredictRealtimeMutation } from "@/core/api/inferenceApi";
import { cn } from "@/shared/lib/utils";
import { input, primaryPill } from "../lib/ui";
import { useApiErrorText } from "./useApiErrorText";

/** Chữ số thì gửi dạng số, còn lại giữ nguyên chữ - backend tự ép kiểu theo model. */
function coerce(value: string): string | number {
  const trimmed = value.trim();
  return trimmed !== "" && !Number.isNaN(Number(trimmed)) ? Number(trimmed) : trimmed;
}

/**
 * Form dự đoán sinh từ danh sách feature thật của model (GET .../deployment,
 * lấy từ config.list_feature của job). Model phải được kích hoạt trước.
 */
export default function InferenceForm({ jobId, activated }: { jobId: string; activated: boolean }) {
  const t = useTranslations("Agent.predict");
  const errorText = useApiErrorText();
  const deployment = useGetModelDeploymentInfoQuery(jobId);
  const [predict, prediction] = usePredictRealtimeMutation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [missing, setMissing] = useState<string[]>([]);

  if (deployment.isLoading) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-automl-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> {t("loading")}
      </p>
    );
  }
  if (deployment.error) return <p className="text-xs text-agent-error">{errorText(deployment.error)}</p>;

  const info = deployment.data?.data;
  const features = info?.features ?? [];
  const active = activated || info?.activate === 1;
  if (!active) return <p className="text-xs text-agent-warning">{t("needActivate")}</p>;
  if (!features.length) return <p className="text-xs text-agent-warning">{t("noFeatures")}</p>;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const empty = features.filter((name) => !(values[name] ?? "").trim());
    setMissing(empty);
    if (empty.length) return;
    const row = Object.fromEntries(features.map((name) => [name, coerce(values[name])]));
    try {
      await predict({ jobId, data: [row] }).unwrap();
    } catch {
      // Lỗi hiện qua prediction.error bên dưới.
    }
  };

  const result = prediction.data?.data;

  return (
    <form onSubmit={submit} noValidate className="space-y-2.5">
      <p className="text-[11px] text-automl-muted">{t("hint")}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {features.map((name) => {
          const id = `predict-${jobId}-${name}`;
          const invalid = missing.includes(name);
          return (
            <div key={name} className="flex flex-col gap-1">
              <label htmlFor={id} className="truncate font-mono text-[11px] text-automl-muted-strong" title={name}>
                {name}
              </label>
              <input
                id={id}
                value={values[name] ?? ""}
                onChange={(event) => setValues((prev) => ({ ...prev, [name]: event.target.value }))}
                aria-invalid={invalid}
                className={cn(input, "w-full", invalid && "border-agent-error")}
              />
            </div>
          );
        })}
      </div>
      {missing.length > 0 && (
        <p role="alert" className="text-xs text-agent-error">{t("missing", { fields: missing.join(", ") })}</p>
      )}
      <button type="submit" disabled={prediction.isLoading} className={primaryPill}>
        {prediction.isLoading && <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden />}
        {prediction.isLoading ? t("running") : t("run")}
      </button>
      {prediction.error && <p role="alert" className="text-xs text-agent-error">{errorText(prediction.error)}</p>}
      {result && (
        <div className="rounded-xl bg-agent-success-soft px-3 py-2 text-xs text-agent-success" aria-live="polite">
          <p className="font-semibold">
            {t("result")}: <span className="font-mono">{result.predictions.map(String).join(", ")}</span>
          </p>
          <p className="mt-0.5 opacity-80">
            {result.model_name} · {t("latency", { ms: Math.round(result.latency_ms) })}
          </p>
        </div>
      )}
    </form>
  );
}
