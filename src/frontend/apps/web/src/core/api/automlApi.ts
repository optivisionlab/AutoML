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
      transformResponse: (response: any) => {
        const raw = response?.data || response;
        if (raw && typeof raw === "object" && "features" in raw) {
          return raw as FeaturesResponse;
        }
        return { features: (raw as FeatureMap) || {} };
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
      },
      providesTags: (_result, _error, datasetId) => [
        { type: "AutoML", id: `preview-${datasetId}` },
      ],
    }),

    // Các metric
    getMetrics: builder.query<MetricsResponse, string>({
      query: (problemType) => ({
        url: `/api/v1/datasets/metrics`,
        params: {
          problem_type: problemType,
        },
      }),
      transformResponse: (res: any, _meta: any, problemType: string): MetricsResponse => {
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
        const config = payload.config || payload;
        return {
          url: `/api/v1/datasets/${datasetId}/training`,
          method: "POST",
          data: {
            choose: config.choose,
            problem_type: config.problem_type || config.problemType,
            target: config.target,
            list_feature: config.list_feature || config.features,
            metric_sort: config.metric_sort,
            search_algorithm: config.search_algorithm || "tpe_search",
            timeout: config.timeout,
          },
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
