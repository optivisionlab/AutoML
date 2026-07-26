import { baseApi } from "./baseApi";

export type FeatureMap = Record<string, boolean>;
export type MetricMap = Record<string, string>;

// Features
type FeaturesResponse = {
  features: FeatureMap;
};

// Các metric nhận
type MetricsResponse = {
  metrics: MetricMap;
};

// Data nhận đc
type DataPreviewResponse = {
  rows: number;
  data: Record<string, unknown>[];
};

// Các tham số nhận đc
type StartTrainingResponse = {
  status: string;
  message: string;
  job_id: string;
};

export const automlApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Lấy các feture
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

    // Lấy trc data priview
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
