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
<<<<<<< HEAD
      transformResponse: (response: any) => {
        const raw = response?.data || response;
        if (raw && typeof raw === "object" && "features" in raw) {
          return raw as FeaturesResponse;
        }
        return { features: (raw as FeatureMap) || {} };
=======
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
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
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
<<<<<<< HEAD
      transformResponse: (response: any) => {
        const payload = response?.data || response;
        if (payload && typeof payload === "object") {
          const list = payload.data || payload.records || [];
          return {
            ...payload,
            data: list,
            records: list,
          };
        }
        return payload;
=======
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
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
      },
      providesTags: (_result, _error, datasetId) => [
        { type: "AutoML", id: `preview-${datasetId}` },
      ],
    }),

    // 4.2 GET /api/v1/datasets/metrics (Problem Metrics)
    getMetrics: builder.query<MetricsResponse, string>({
      query: (problemType) => ({
<<<<<<< HEAD
        url: `/api/v1/datasets/metrics`,
=======
        url: "/api/v1/datasets/metrics",
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
        params: {
          problem_type: problemType,
        },
      }),
      transformResponse: (res: any, _meta: any, problemType: string): MetricsResponse => {
<<<<<<< HEAD
        const list: string[] = res?.data?.metrics || [];
        if (list.length > 0) {
          const metricsMap: Record<string, string> = {};
          list.forEach((m: string) => {
            metricsMap[m] = m;
          });
          return { metrics: metricsMap };
        }

        // Fallback if API response is empty
        const fallbackMap: Record<string, string> =
          problemType === "classification"
            ? {
                accuracy: "accuracy",
                f1: "f1",
                precision: "precision",
                recall: "recall",
              }
            : {
                r2: "r2",
                rmse: "rmse",
                mae: "mae",
                mse: "mse",
                mape: "mape",
              };
        return { metrics: fallbackMap };
=======
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
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
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
<<<<<<< HEAD
          data: {
            choose: config.choose,
            problem_type: config.problem_type || config.problemType,
            target: config.target,
            list_feature: config.list_feature || config.features,
            metric_sort: config.metric_sort,
            search_algorithm: config.search_algorithm || "tpe_search",
            timeout: config.timeout,
          },
=======
          data: body,
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
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
