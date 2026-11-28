"use client";

import { FormEvent, useId, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { useGetDatasetDataPreviewQuery } from "@/core/api/datasetApi";
import { useGetModelDeploymentInfoQuery, usePredictRealtimeMutation } from "@/core/api/inferenceApi";
import { cn } from "@/shared/lib/utils";
import { coerceFeature, featureKinds, shortBackendError, stepUnit, timeSeriesHint } from "../lib/predict";
import { input, primaryPill } from "../lib/ui";
import { useApiErrorText } from "./useApiErrorText";

// time_series: dataset không quá số ô này (dòng x cột) thì tải đủ để tính mốc cuối
// đúng như backend; lớn hơn thì chỉ ước tính từ preview.
const SERIES_FULL_CELLS = 200_000;

/**
 * Form dự đoán sinh từ danh sách feature thật của model (GET .../deployment,
 * lấy từ config.list_feature của job). Model phải được kích hoạt trước.
 */
export default function InferenceForm({
  jobId,
  activated,
  problemType,
  datasetId,
  onInactive,
}: {
  jobId: string;
  activated: boolean;
  problemType?: string;
  datasetId?: string;
  /** Backend báo model đã bị tắt (403): thẻ job phải hiện lại nút kích hoạt. */
  onInactive?: () => void;
}) {
  const timeSeries = problemType === "time_series";
  const t = useTranslations("Agent.predict");
  const errorText = useApiErrorText();
  const deployment = useGetModelDeploymentInfoQuery(jobId);
  // Job chỉ biết qua job_watch / job_done có thể thiếu datasetId: /deployment cũng trả dataset_id.
  const sourceDatasetId = datasetId ?? deployment.data?.data?.dataset_id ?? undefined;
  // id ô nhập phải duy nhất trên trang: cùng một job có thể mở form ở cả thẻ trong chat lẫn panel.
  const idPrefix = useId();
  // Preview dataset (xem lib/predict.ts): kiểu thật của từng cột lúc train, và với
  // time_series là mốc cuối + bước thời gian để chỉ người dùng nhập mốc hợp lệ.
  const preview = useGetDatasetDataPreviewQuery({ datasetId: sourceDatasetId ?? "", numRows: 50 }, { skip: !sourceDatasetId });
  // transformResponse ở datasetApi trả { rows, data: [...] } chứ không bọc BaseResponse.
  const previewPayload = preview.data as unknown as { rows?: number; data?: Record<string, unknown>[] } | undefined;
  const previewRows = previewPayload?.data;
  const totalRows = previewPayload?.rows;
  const columnCount = previewRows?.[0] ? Object.keys(previewRows[0]).length : 1;
  const wantFull =
    timeSeries &&
    Boolean(sourceDatasetId) &&
    typeof totalRows === "number" &&
    totalRows > (previewRows?.length ?? 0) &&
    totalRows * columnCount <= SERIES_FULL_CELLS;
  const full = useGetDatasetDataPreviewQuery({ datasetId: sourceDatasetId ?? "", numRows: totalRows ?? 0 }, { skip: !wantFull });
  // Đang tải đủ dataset: chưa hiện gợi ý (khỏi nhảy từ ước tính sang số đúng). Tải lỗi thì đành ước tính.
  const seriesRows = wantFull
    ? full.isError
      ? previewRows
      : (full.data as unknown as { data?: Record<string, unknown>[] } | undefined)?.data
    : previewRows;
  // Chờ biết kiểu cột rồi mới cho gửi: gửi sớm thì "001" của cột chữ vẫn bị đoán thành số.
  // Không lấy được preview (lỗi) thì mới đành đoán như cũ - cột số là trường hợp phổ biến,
  // và bộ tiền xử lý của backend không tự đổi chữ số thành số.
  const typesPending = Boolean(sourceDatasetId) && !timeSeries && (preview.isLoading || preview.isFetching);
  // Tính một lần cho mỗi bộ dữ liệu, không phải mỗi lần gõ phím: với dataset tải đủ,
  // việc này đọc và sắp xếp hàng chục nghìn mốc thời gian.
  const featureList = deployment.data?.data?.features;
  const series = useMemo(
    () => (timeSeries ? timeSeriesHint(seriesRows, featureList ?? [], totalRows) : null),
    [timeSeries, seriesRows, featureList, totalRows],
  );
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
    if (typesPending) return;
    const empty = features.filter((name) => !(values[name] ?? "").trim());
    setMissing(empty);
    if (empty.length) return;
    const kinds = featureKinds(previewRows, features);
    const row = Object.fromEntries(features.map((name) => [name, coerceFeature(values[name] ?? "", kinds[name], timeSeries)]));
    try {
      await predict({ jobId, data: [row] }).unwrap();
    } catch (error) {
      // Lỗi hiện qua prediction.error bên dưới. 403 = model đã bị tắt (có thể ở nơi khác):
      // cờ "đã kích hoạt" đang giữ là cũ - báo thẻ job và tải lại thông tin deployment.
      if ((error as { status?: unknown } | null)?.status === 403) {
        onInactive?.();
        deployment.refetch();
      }
    }
  };

  const result = prediction.data?.data;
  const step = series ? stepUnit(series.stepMs) : null;
  const stepText = step ? t(`step.${step.unit}`, { n: step.n }) : "";
  // Lỗi backend kèm cả traceback của worker: chỉ hiện câu lỗi; lỗi mốc thời gian thì nói rõ mốc hợp lệ.
  const errorMessage = (() => {
    if (!prediction.error) return null;
    // Backend trả 403 khi model đã bị tắt (có thể tắt ở nơi khác sau khi form đã mở) -
    // nói đúng lý do thay vì câu chung "không có quyền với job này".
    if ((prediction.error as { status?: unknown }).status === 403) return t("needActivate");
    const raw = errorText(prediction.error);
    const short = shortBackendError(raw);
    if (timeSeries && short.startsWith("Timestamps must come after")) {
      if (!series) return t("seriesBadTimestampNoHint");
      const values = { last: series.last, step: stepText, next: series.next };
      return series.estimated ? t("seriesBadTimestampEstimated", values) : t("seriesBadTimestamp", values);
    }
    if (timeSeries && short.startsWith("Cannot forecast more than")) return t("seriesTooFar", { max: 365 });
    return short === raw ? raw : t("backendError", { detail: short });
  })();

  return (
    <form onSubmit={submit} noValidate className="space-y-2.5">
      <p className="text-[11px] text-automl-muted">{timeSeries ? t("timeSeriesHint") : t("hint")}</p>
      {series && (
        <p className="text-[11px] text-automl-muted-strong">
          {t(series.estimated ? "seriesLastEstimated" : "seriesLast", { last: series.last, step: stepText })}{" "}
          <button
            type="button"
            onClick={() => setValues((prev) => ({ ...prev, [series.column]: series.next }))}
            className="agent-focus rounded font-semibold text-agent-primary underline-offset-2 hover:underline"
          >
            {t("seriesUseNext", { next: series.next })}
          </button>
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {features.map((name, index) => {
          const id = `${idPrefix}-predict-${index}`;
          const invalid = missing.includes(name);
          return (
            <div key={name} className="flex flex-col gap-1">
              <label htmlFor={id} className="truncate font-mono text-[11px] text-automl-muted-strong" title={name}>
                {name}
              </label>
              <input
                id={id}
                value={values[name] ?? ""}
                placeholder={series?.column === name ? series.next : undefined}
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
      <button type="submit" disabled={prediction.isLoading || typesPending} className={primaryPill}>
        {(prediction.isLoading || typesPending) && <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden />}
        {prediction.isLoading ? t("running") : typesPending ? t("loading") : t("run")}
      </button>
      {errorMessage && <p role="alert" className="break-words text-xs text-agent-error">{errorMessage}</p>}
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
