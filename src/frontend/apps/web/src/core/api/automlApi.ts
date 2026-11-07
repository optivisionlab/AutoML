import {
  type FeatureMap,
  type MetricMap,
  type FeaturesResponse,
  type MetricsResponse,
  type DataPreviewResponse,
  type StartTrainingResponse,
  type StartTrainingPayload,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  FeatureMap,
  MetricMap,
  FeaturesResponse,
  MetricsResponse,
  DataPreviewResponse,
  StartTrainingResponse,
  StartTrainingPayload,
};

export const automlApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 3.8 Lấy các feature và gợi ý target
    getFeatures: builder.query<
      FeaturesResponse,
      { datasetId: string; problemType: string }
    >({
      query: ({ datasetId, problemType }) => ({
        url: `/api/v1/datasets/${datasetId}/features`,
        params: {
          problem_type: problemType,
        },
      }),
      transformResponse: (response: any): FeaturesResponse => {
        const raw = response?.data?.features ?? response?.data ?? response?.features ?? response;
        const featuresMap: Record<string, boolean> = {};

        if (Array.isArray(raw)) {
          raw.forEach((col: string) => {
            featuresMap[col] = true;
          });
        } else if (raw && typeof raw === "object") {
          Object.entries(raw).forEach(([k, v]) => {
            if (k !== "success" && k !== "message" && k !== "status" && k !== "meta") {
              featuresMap[k] = Boolean(v);
            }
          });
        }

        return { features: featuresMap };
      },
      providesTags: (_result, _error, { datasetId }) => [
        { type: "AutoML", id: `features-${datasetId}` },
      ],
    }),

    // 3.9 Lấy data preview
    getDatasetPreview: builder.query<DataPreviewResponse, string>({
      query: (datasetId) => ({
        url: `/api/v1/datasets/${datasetId}/data`,
        params: {
          num_rows: 50,
        },
      }),
      transformResponse: (response: any): DataPreviewResponse => {
        const raw = response?.data || response;
        const rows =
          raw?.total_rows ??
          raw?.rows ??
          (Array.isArray(raw?.data) ? raw.data.length : Array.isArray(raw) ? raw.length : 0);
        const data = Array.isArray(raw?.data)
          ? raw.data
          : Array.isArray(raw?.records)
            ? raw.records
            : Array.isArray(raw)
              ? raw
              : [];
        return { rows, data };
      },
      providesTags: (_result, _error, datasetId) => [
        { type: "AutoML", id: `preview-${datasetId}` },
      ],
    }),

    // 4.2 GET /api/v1/datasets/metrics (Problem Metrics)
    getMetrics: builder.query<MetricsResponse, string>({
      query: (problemType) => ({
        url: "/api/v1/datasets/metrics",
        params: {
          problem_type: problemType,
        },
      }),
      transformResponse: (res: any, _meta: any, problemType: string): MetricsResponse => {
        const rawMetrics = res?.data?.metrics || res?.metrics;
        const metricsMap: Record<string, string> = {};

        if (Array.isArray(rawMetrics) && rawMetrics.length > 0) {
          rawMetrics.forEach((m: string) => {
            metricsMap[m] = m;
          });
        } else if (rawMetrics && typeof rawMetrics === "object" && !Array.isArray(rawMetrics)) {
          Object.assign(metricsMap, rawMetrics);
        } else {
          // Fallback defaults aligned with backend assets config
          const fallbackMetrics =
            problemType === "classification"
              ? [
                  "accuracy",
                  "balanced_accuracy",
                  "precision_macro",
                  "precision_weighted",
                  "recall_macro",
                  "recall_weighted",
                  "f1_macro",
                  "f1_weighted",
                ]
              : problemType === "time_series"
                ? ["mse", "mae", "rmse", "r2"]
                : ["mse", "mae", "mape", "r2"];

          fallbackMetrics.forEach((m) => {
            metricsMap[m] = m;
          });
        }

        return { metrics: metricsMap };
      },
      providesTags: (_result, _error, problemType) => [
        { type: "AutoML", id: `metrics-${problemType}` },
      ],
    }),

    // 3.10 Bắt đầu train
    startTrainingJob: builder.mutation<
      StartTrainingResponse,
      { id_data: string; id_user?: string; config: any } | any
    >({
      query: (payload) => {
        const datasetId = payload.id_data || payload.id;
        const rawConfig = payload.config || payload;

        let listFeature = rawConfig.list_feature || rawConfig.features || [];
        if (typeof listFeature === "string") {
          try {
            listFeature = JSON.parse(listFeature);
          } catch {
            listFeature = [listFeature];
          }
        }

        const body = {
          choose: rawConfig.choose || "new_model",
          problem_type: rawConfig.problem_type || rawConfig.problemType || "classification",
          target: rawConfig.target,
          list_feature: Array.isArray(listFeature) ? listFeature : [],
          metric_sort: rawConfig.metric_sort,
          search_algorithm: rawConfig.search_algorithm || "bayesian_search",
          ...(rawConfig.timeout !== undefined ? { timeout: rawConfig.timeout } : {}),
        };

        return {
          url: `/api/v1/datasets/${datasetId}/training`,
          method: "POST",
          data: body,
        };
      },
      transformResponse: (response: any) => {
        return response?.data || response;
      },
      invalidatesTags: ["Job"],
    }),
  }),
});

export const {
  useGetDatasetPreviewQuery,
  useGetFeaturesQuery,
  useGetMetricsQuery,
  useStartTrainingJobMutation,
} = automlApi;
