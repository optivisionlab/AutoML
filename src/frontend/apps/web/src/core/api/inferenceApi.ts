import axios from "axios";
import {
  type ActivateModelPayload,
  type ActiveModelsResponse,
  type DeploymentInfoResponse,
  type JobsListParams,
  type JobsListResponse,
  type PredictionFile,
  type RealtimePredictPayload,
  type RealtimePredictResponse,
} from "@automl/domain";
import { appendUniversalFile, resolveFileName } from "@automl/api";
import { axiosClient, baseApi } from "./baseApi";

export type {
  ActivateModelPayload,
  ActiveModelsResponse,
  DeploymentInfoResponse,
  JobsListParams,
  JobsListResponse,
  PredictionFile,
  RealtimePredictPayload,
  RealtimePredictResponse,
};

export const inferenceApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 5.1 GET /api/v1/inference/jobs
    getTrainingJobs: builder.query<JobsListResponse, JobsListParams | void>({
      query: (params) => ({
        url: "/api/v1/inference/jobs",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
          sort_name: params?.sort_name || undefined,
          sort_time: params?.sort_time || "desc",
        },
      }),
      providesTags: ["Job"],
    }),

    // 5.2 GET /api/v1/inference/models
    getActiveModels: builder.query<ActiveModelsResponse, JobsListParams | void>({
      query: (params) => ({
        url: "/api/v1/inference/models",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
        },
      }),
      providesTags: ["Inference", "Job"],
    }),

    // 5.3 PUT /api/v1/inference/models/{id}/activation
    activateModel: builder.mutation<
      DeploymentInfoResponse,
      { id?: string; jobId?: string; activate: 0 | 1 }
    >({
      query: ({ id, jobId, activate }) => {
        const targetId = id || jobId;
        return {
          url: `/api/v1/inference/models/${targetId}/activation`,
          method: "PUT",
          data: { activate },
        };
      },
      invalidatesTags: (_result, _error, { id, jobId }) => [
        "Inference",
        "Job",
        { type: "Job", id: id || jobId },
      ],
    }),

    // 5.4 GET /api/v1/inference/models/{id}/deployment
    getModelDeploymentInfo: builder.query<DeploymentInfoResponse, string>({
      query: (id) => ({
        url: `/api/v1/inference/models/${id}/deployment`,
      }),
      providesTags: (_result, _error, id) => [
        { type: "Inference", id },
        { type: "Job", id },
      ],
    }),

    // 5.5 POST /api/v1/inference/models/{id}/predict
    predictRealtime: builder.mutation<
      RealtimePredictResponse,
      { id?: string; jobId?: string; data: Array<Record<string, unknown>> }
    >({
      query: ({ id, jobId, data }) => {
        const targetId = id || jobId;
        return {
          url: `/api/v1/inference/models/${targetId}/predict`,
          method: "POST",
          data: { data },
        };
      },
    }),

    // 5.6 POST /api/v1/inference/models/{id}/predict/file
    predictBatchFile: builder.mutation<
      PredictionFile,
      { id?: string; jobId?: string; file: File | Blob }
    >({
      async queryFn({ id, jobId, file }) {
        const targetId = id || jobId;
        const formData = new FormData();
        appendUniversalFile(formData, "file", file);

        try {
          const response = await axiosClient.post(
            `/api/v1/inference/models/${targetId}/predict/file`,
            formData,
            { responseType: "blob" },
          );

          return {
            data: {
              blob: response.data,
              fileName: resolveFileName(
                response.headers["content-disposition"],
                "predicted_result.csv",
              ),
            },
          };
        } catch (error) {
          if (axios.isAxiosError(error)) {
            return {
              error: {
                status: error.response?.status,
                data: error.response?.data ?? error.message,
              },
            };
          }

          return { error: { data: "Prediction failed" } };
        }
      },
      invalidatesTags: ["Inference"],
    }),

    // Legacy method aliases
    inferenceModel: builder.mutation<unknown, { jobId: string; file: File }>({
      query: ({ jobId, file }) => {
        const formData = new FormData();
        appendUniversalFile(formData, "file", file);

        return {
          url: `/api/v1/inference/models/${jobId}/predict/file`,
          method: "POST",
          data: formData,
        };
      },
      invalidatesTags: ["Inference"],
    }),
    runPrediction: builder.mutation<PredictionFile, { jobId: string; file: File }>({
      async queryFn({ jobId, file }) {
        const formData = new FormData();
        appendUniversalFile(formData, "file", file);

        try {
          const response = await axiosClient.post(
            `/api/v1/inference/models/${jobId}/predict/file`,
            formData,
            { responseType: "blob" },
          );

          return {
            data: {
              blob: response.data,
              fileName: resolveFileName(
                response.headers["content-disposition"],
                "predicted_result.csv",
              ),
            },
          };
        } catch (error) {
          if (axios.isAxiosError(error)) {
            return {
              error: {
                status: error.response?.status,
                data: error.response?.data ?? error.message,
              },
            };
          }

          return { error: { data: "Prediction failed" } };
        }
      },
      invalidatesTags: ["Inference"],
    }),
    cancelPrediction: builder.mutation<unknown, string>({
      query: () => ({
        url: "/api/v1/notifications",
      }),
    }),
  }),
});

export const {
  useActivateModelMutation,
  useCancelPredictionMutation,
  useGetActiveModelsQuery,
  useGetModelDeploymentInfoQuery,
  useGetTrainingJobsQuery,
  useInferenceModelMutation,
  useLazyGetActiveModelsQuery,
  useLazyGetModelDeploymentInfoQuery,
  useLazyGetTrainingJobsQuery,
  usePredictBatchFileMutation,
  usePredictRealtimeMutation,
  useRunPredictionMutation,
} = inferenceApi;
