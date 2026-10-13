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
        return response?.data || response;
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
        return response?.data || response;
      },
      providesTags: (_result, _error, datasetId) => [
        { type: "AutoML", id: `preview-${datasetId}` },
      ],
    }),

    // Các metric
    getMetrics: builder.query<MetricsResponse, string>({
      query: (problemType) => ({
        url: `/api/v1/datasets/default`,
        params: {
          problem_type: problemType,
        },
      }),
      transformResponse: (_res: any, _meta: any, problemType: string): MetricsResponse => {
        const metricsMap: Record<string, string> =
          problemType === "classification"
            ? {
                Accuracy: "accuracy",
                F1: "f1",
                Precision: "precision",
                Recall: "recall",
              }
            : {
                R2: "r2",
                RMSE: "rmse",
                MAE: "mae",
                MSE: "mse",
                MAPE: "mape",
              };
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
        const config = payload.config || payload;
        return {
          url: `/api/v1/datasets/${datasetId}/training`,
          method: "POST",
          data: {
            config: {
              choose: config.choose,
              problem_type: config.problem_type || config.problemType,
              target: config.target,
              list_feature: config.list_feature || config.features,
              metric_sort: config.metric_sort,
              search_algorithm: config.search_algorithm || "bayesian_search",
            },
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
