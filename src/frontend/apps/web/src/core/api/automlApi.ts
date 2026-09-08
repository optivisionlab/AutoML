import {
  type FeatureMap,
  type MetricMap,
  type FeaturesResponse,
  type MetricsResponse,
  type DataPreviewResponse,
  type StartTrainingResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  FeatureMap,
  MetricMap,
  FeaturesResponse,
  MetricsResponse,
  DataPreviewResponse,
  StartTrainingResponse,
};

export const automlApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Lấy các feature
    getFeatures: builder.query<
      FeaturesResponse,
      { datasetId: string; problemType: string }
    >({
      query: ({ datasetId, problemType }) => ({
        url: "/v2/auto/features",
        params: {
          id_data: datasetId,
          problem_type: problemType,
        },
      }),
      providesTags: (_result, _error, { datasetId }) => [
        { type: "AutoML", id: `features-${datasetId}` },
      ],
    }),

    // Lấy data preview
    getDatasetPreview: builder.query<DataPreviewResponse, string>({
      query: (datasetId) => ({
        url: "/v2/auto/data",
        params: {
          id_data: datasetId,
        },
      }),
      providesTags: (_result, _error, datasetId) => [
        { type: "AutoML", id: `preview-${datasetId}` },
      ],
    }),

    // Các metric
    getMetrics: builder.query<MetricsResponse, string>({
      query: (problemType) => ({
        url: "/v2/auto/metrics",
        params: {
          problem_type: problemType,
        },
      }),
      providesTags: (_result, _error, problemType) => [
        { type: "AutoML", id: `metrics-${problemType}` },
      ],
    }),

    // Bắt đầu train
    startTrainingJob: builder.mutation<StartTrainingResponse, unknown>({
      query: (payload) => ({
        url: "/v2/auto/jobs/training",
        method: "POST",
        data: payload,
      }),
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
