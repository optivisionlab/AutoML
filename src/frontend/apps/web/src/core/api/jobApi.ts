import {
  type BaseResponse,
  type CancelJobResponse,
  type TrainingJob,
  type JobConfig,
  type JobDetailPayload,
  type JobDetailResponse,
  type OtherModelScore,
  type GetJobsOffsetParams,
  type GetPipelineSamplePayload,
  type PipelineData,
  type PipelineSampleResponse,
  type JobsListParams,
  type JobsListResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  CancelJobResponse,
  TrainingJob,
  JobConfig,
  JobDetailPayload,
  JobDetailResponse,
  OtherModelScore,
  GetJobsOffsetParams,
  GetPipelineSamplePayload,
  PipelineData,
  PipelineSampleResponse,
  JobsListParams,
  JobsListResponse,
};

const unwrapJobResponse = (
  response: JobDetailResponse | JobDetailPayload | TrainingJob | PipelineData,
): JobDetailPayload => {
  if (
    response &&
    typeof response === "object" &&
    "data" in response &&
    response.data &&
    typeof response.data === "object" &&
    !("_id" in response) &&
    !("read_dataset" in response) &&
    !("train" in response)
  ) {
    return response.data as JobDetailPayload;
  }
  return response as JobDetailPayload;
};

export const jobApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 5.1 GET /api/v1/inference/jobs
    getJobs: builder.query<JobsListResponse, JobsListParams | void>({
      query: (params) => ({
        url: "/api/v1/inference/jobs",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
          sort_name: params?.sort_name || undefined,
          sort_time: params?.sort_time || "desc",
        },
      }),
      transformResponse: (response: JobsListResponse) => ({
        ...response,
        data: (response?.data || []).map((job) => ({
          ...job,
          job_id: job.job_id || job._id,
        })),
      }),
      providesTags: ["Job"],
    }),

    // GET /api/v1/inference/jobs/{id} (returns PipelineData v2.0.0 inside BaseResponse.data)
    getJobDetail: builder.query<JobDetailPayload, string>({
      query: (id) => ({
        url: `/api/v1/inference/jobs/${id}`,
      }),
      transformResponse: (response: JobDetailResponse | JobDetailPayload) =>
        unwrapJobResponse(response),
      providesTags: (_result, _error, id) => [{ type: "Job", id }],
    }),

    // GET /api/v1/inference/jobs/{id}/pipeline
    getJobPipeline: builder.query<PipelineData, string>({
      query: (id) => ({
        url: `/api/v1/inference/jobs/${id}/pipeline`,
      }),
      transformResponse: (response: JobDetailResponse | PipelineData) =>
        unwrapJobResponse(response) as PipelineData,
      providesTags: (_result, _error, id) => [
        { type: "Job", id: `pipeline-${id}` },
        { type: "Job", id },
      ],
    }),

    // POST /api/v1/inference/jobs/{id}/cancel
    cancelTrainingJob: builder.mutation<
      BaseResponse<{ status: number | string; job_id: string }>,
      string
    >({
      query: (jobId) => ({
        url: `/api/v1/inference/jobs/${jobId}/cancel`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, jobId) => [
        "Job",
        { type: "Job", id: jobId },
        "Inference",
      ],
    }),

    // 6.2 POST /api/v1/inference/jobs/{id}/cancel (alias)
    cancelJob: builder.mutation<CancelJobResponse, string>({
      query: (jobId) => ({
        url: `/api/v1/inference/jobs/${jobId}/cancel`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, jobId) => [
        "Job",
        { type: "Job", id: jobId },
        "Inference",
      ],
    }),

    // Legacy hook compatibility: returns array of TrainingJob
    getLegacyJobsByUserId: builder.query<TrainingJob[], string | void>({
      query: () => ({
        url: "/api/v1/inference/jobs",
        params: { current_page: 1, page_size: 100, sort_time: "desc" },
      }),
      transformResponse: (response: JobsListResponse | TrainingJob[]) => {
        const list = Array.isArray(response) ? response : response?.data || [];
        return list.map((job) => ({
          ...job,
          job_id: job.job_id || job._id,
        }));
      },
      providesTags: ["Job"],
    }),

    getJobsOffset: builder.query<unknown, GetJobsOffsetParams>({
      query: ({ page = 1, limit = 10 }) => ({
        url: "/api/v1/inference/jobs",
        params: { current_page: page, page_size: limit, sort_time: "desc" },
      }),
      providesTags: ["Job"],
    }),

    // Calls GET /api/v1/inference/jobs/{id}
    getJobInfo: builder.query<JobDetailPayload, string>({
      query: (id) => ({
        url: `/api/v1/inference/jobs/${id}`,
      }),
      transformResponse: (response: JobDetailResponse | JobDetailPayload) =>
        unwrapJobResponse(response),
      providesTags: (_result, _error, id) => [{ type: "Job", id }],
    }),

    getPipelineSample: builder.query<
      PipelineSampleResponse,
      GetPipelineSamplePayload
    >({
      query: (payload) => ({
        url: "/get-pipeline-sample",
        method: "POST",
        data: payload,
      }),
      providesTags: (_result, _error, arg) => [
        { type: "Job", id: arg.job_id || arg.problem_type },
      ],
    }),
  }),
});

export const {
  useCancelJobMutation,
  useCancelTrainingJobMutation,
  useGetJobDetailQuery,
  useGetJobInfoQuery,
  useGetJobPipelineQuery,
  useGetJobsOffsetQuery,
  useGetJobsQuery,
  useGetLegacyJobsByUserIdQuery,
  useGetPipelineSampleQuery,
  useLazyGetJobDetailQuery,
  useLazyGetJobInfoQuery,
  useLazyGetJobPipelineQuery,
  useLazyGetJobsQuery,
  useLazyGetLegacyJobsByUserIdQuery,
  useLazyGetPipelineSampleQuery,
} = jobApi;
