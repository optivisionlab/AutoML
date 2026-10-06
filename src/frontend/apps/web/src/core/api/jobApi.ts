import {
  type TrainingJob,
  type JobConfig,
  type OtherModelScore,
  type GetJobsOffsetParams,
  type GetPipelineSamplePayload,
  type PipelineSampleResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  TrainingJob,
  JobConfig,
  OtherModelScore,
  GetJobsOffsetParams,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
};

export const jobApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getJobsOffset: builder.query<unknown, GetJobsOffsetParams>({
      query: ({ userId, page = 1, limit = 5 }) => ({
        url: `/v2/auto/jobs/offset/${userId}`,
        params: { page, limit },
      }),
      providesTags: ["Job"],
    }),
    getJobInfo: builder.query<TrainingJob, string>({
      query: (id) => ({
        url: "/get-job-info",
        method: "POST",
        params: { id },
      }),
      providesTags: (_result, _error, id) => [{ type: "Job", id }],
    }),
    getLegacyJobsByUserId: builder.query<TrainingJob[], string>({
      query: (userId) => ({
        url: "/get-list-job-by-userId",
        method: "POST",
        params: { user_id: userId },
      }),
      providesTags: ["Job"],
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
  useGetLegacyJobsByUserIdQuery,
  useGetPipelineSampleQuery,
  useLazyGetPipelineSampleQuery,
} = jobApi;

