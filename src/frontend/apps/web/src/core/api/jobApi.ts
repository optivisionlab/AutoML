import {
  type TrainingJob,
  type JobConfig,
  type OtherModelScore,
  type GetJobsOffsetParams,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type { TrainingJob, JobConfig, OtherModelScore, GetJobsOffsetParams };

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
  }),
});

export const {
  useGetJobInfoQuery,
  useGetJobsOffsetQuery,
  useGetLegacyJobsByUserIdQuery,
} = jobApi;
