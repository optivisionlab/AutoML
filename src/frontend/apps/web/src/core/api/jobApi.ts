import {
  type TrainingJob,
  type JobConfig,
  type OtherModelScore,
  type GetJobsOffsetParams,
  type GetPipelineSamplePayload,
  type PipelineSampleResponse,
  type JobsListParams,
  type JobsListResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  TrainingJob,
  JobConfig,
  OtherModelScore,
  GetJobsOffsetParams,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
  JobsListParams,
  JobsListResponse,
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
      providesTags: ["Job"],
    }),

    // Legacy hook compatibility: returns array of TrainingJob
    getLegacyJobsByUserId: builder.query<TrainingJob[], string | void>({
      query: () => ({
        url: "/api/v1/inference/jobs",
        params: { current_page: 1, page_size: 100 },
      }),
      transformResponse: (response: JobsListResponse) => response?.data || [],
      providesTags: ["Job"],
    }),

    getJobsOffset: builder.query<unknown, GetJobsOffsetParams>({
      query: ({ page = 1, limit = 10 }) => ({
        url: "/api/v1/inference/jobs",
        params: { current_page: page, page_size: limit },
      }),
      providesTags: ["Job"],
    }),

    getJobInfo: builder.query<TrainingJob, string>({
      query: (id) => ({
        url: `/api/v1/inference/models/${id}/deployment`,
      }),
      transformResponse: (response: any) => response?.data || response,
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
  useGetJobInfoQuery,
  useGetJobsOffsetQuery,
  useGetJobsQuery,
  useGetLegacyJobsByUserIdQuery,
  useGetPipelineSampleQuery,
  useLazyGetJobInfoQuery,
  useLazyGetJobsQuery,
  useLazyGetLegacyJobsByUserIdQuery,
  useLazyGetPipelineSampleQuery,
} = jobApi;
