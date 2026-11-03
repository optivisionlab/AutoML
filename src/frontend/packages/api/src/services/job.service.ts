import { AxiosInstance } from "axios";
import {
  JobsListParams,
  JobsListResponse,
  TrainingJob,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
} from "@automl/domain";

export const createJobService = (client: AxiosInstance) => ({
  // 5.1 GET /api/v1/inference/jobs
  getJobs: async (params?: JobsListParams): Promise<JobsListResponse> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
        sort_name: params?.sort_name || undefined,
        sort_time: params?.sort_time || "desc",
      },
    });
    return res.data;
  },

  // Legacy compatibility methods
  getJobsOffset: async (params: any): Promise<unknown> => {
    const res = await client.get("/api/v1/inference/jobs", {
      params: { current_page: params?.page ?? 1, page_size: params?.limit ?? 10 },
    });
    return res.data;
  },

  getJobInfo: async (id: string): Promise<TrainingJob> => {
    const res = await client.get<any>(`/api/v1/inference/models/${id}/deployment`);
    return res.data?.data || res.data;
  },

  getLegacyJobsByUserId: async (_userId?: string): Promise<TrainingJob[]> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs");
    return (res.data?.data || []) as TrainingJob[];
  },

  getPipelineSample: async (
    payload: GetPipelineSamplePayload,
  ): Promise<PipelineSampleResponse> => {
    const res = await client.post<PipelineSampleResponse>(
      "/get-pipeline-sample",
      payload,
    );
    return res.data;
  },
});
