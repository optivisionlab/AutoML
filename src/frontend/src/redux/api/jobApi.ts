import { baseApi } from "./baseApi";

export type TrainingJob = {
  _id: string;
  job_id: string;
  data?: {
    name?: string;
  };
  config?: {
    choose?: string;
    list_feature?: string[];
    metric_sort?: string;
    problem_type?: string;
    target?: string;
  };
  best_model?: string;
  best_model_id?: string;
  best_params?: unknown;
  best_score?: number;
  create_at?: number;
  model?: unknown;
  orther_model_scores?: {
    model_name: string;
    scores: Record<string, number>;
  }[];
  status: number | string;
};

export const jobApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getJobsOffset: builder.query<
      unknown,
      { userId: string; page?: number; limit?: number }
    >({
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
